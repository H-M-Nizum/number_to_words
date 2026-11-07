# Part of Odoo. See LICENSE file for full copyright and licensing details.
import hashlib
import re
from collections import Counter

from lxml import etree

from odoo import api, fields, models

from ..tools.names import GENERATED_VIEW_PREFIX

MAX_ANCHORS = 300
# Bump it whenever the way places are listed changes: cached places are then refreshed.
PLACES_VERSION = 5
MAX_TEMPLATES = 8
# The labels are translated where they are written (see _kind_label).
KINDS = ['field', 'value', 'block', 'title', 'column']


class NumberToWordsAnchor(models.Model):
    """A place of a report where the words can be inserted, described in plain
    words (so users never have to write an XPath)."""
    _name = 'number.to.words.anchor'
    _description = 'Report Place for Amount in Words'
    _order = 'view_id, sequence, id'

    view_id = fields.Many2one(
        'ir.ui.view', required=True, ondelete='cascade', index=True,
        help="The report template the places were listed for.")
    template_ids = fields.Many2many(
        'ir.ui.view', 'number_to_words_anchor_template_rel', 'anchor_id', 'template_id',
        string="Templates",
        help="The templates that really contain the place (a report often calls other templates, "
             "and its layouts share the same places).")
    sequence = fields.Integer()
    name = fields.Char(string="Place", required=True)
    kind = fields.Selection(
        [('field', "Field"), ('value', "Value"), ('block', "Block"), ('title', "Title"), ('column', "Column")],
        required=True,
    )
    xpath = fields.Char(required=True)
    model_name = fields.Char()
    record_var = fields.Char()
    stamp = fields.Char(help="Fingerprint of the templates the places were read from.")

    # ------------------------------------------------------------------
    # Reading the templates
    # ------------------------------------------------------------------
    @api.model
    def _template_views(self, view):
        views = view | view._get_inheriting_views()
        return views.filtered(lambda v: not (v.name or '').startswith(GENERATED_VIEW_PREFIX))

    @api.model
    def _template_tree(self, view):
        """Combined architecture of the template without our own insertions."""
        tree = view.get_combined_arch()
        tree = tree if isinstance(tree, etree._Element) else etree.fromstring(tree)
        for node in tree.xpath("//*[contains(@class, 'number-to-words')]"):
            node.getparent().remove(node)
        return tree

    @api.model
    def _collect_templates(self, view):
        """The template and the templates it calls (recursively)."""
        View = self.env['ir.ui.view']
        found, queue = View, [view]
        while queue and len(found) < MAX_TEMPLATES:
            current = queue.pop(0)
            if current in found:
                continue
            found |= current
            for node in self._template_tree(current).iter():
                call = node.get('t-call') if isinstance(node.tag, str) else None
                # the layouts of the web module only wrap the content: skip them
                if call and re.fullmatch(r'[\w.]+', call) and not call.startswith('web.'):
                    called = View.search([('key', '=', call), ('type', '=', 'qweb'), ('inherit_id', '=', False)], limit=1)
                    if called:
                        queue.append(called)
        return found

    @api.model
    def _guess_record_var(self, view):
        """The name of the record in the template ('doc', 'o', 'product'...)."""
        counter = Counter()
        for template in self._collect_templates(view.sudo()):
            counter.update(re.findall(r't-(?:field|out|esc)="(\w+)\.', template.arch_db or ''))
        counter.pop('env', None)
        return counter.most_common(1)[0][0] if counter else 'doc'

    @api.model
    def _field_label(self, expression, model_name, record_var):
        """'doc.partner_id.vat' -> 'Customer › Tax ID' when the model is known."""
        prefix = f"{record_var}."
        if not (model_name and record_var and expression.startswith(prefix)):
            return expression
        labels, model = [], model_name
        for part in expression[len(prefix):].split('.'):
            field = self.env['ir.model.fields']._get(model, part) if model else None
            if not field:
                return expression
            labels.append(field.field_description)
            model = field.relation
        return ' › '.join(labels)

    @api.model
    def _kind_label(self, kind):
        return dict(self._fields['kind']._description_selection(self.env))[kind]

    @api.model
    def _extract_places(self, tree, model_name, record_var):
        """Places of one template, in document order.

        Only places of the document itself are listed: what is inside a loop
        (the order lines for example) is repeated for every item, so the
        amount in words could not be placed there.
        """
        places, seen, labels = [], set(), set()
        block_tags = {'div', 'section', 'p', 'span', 'table', 'h1', 'h2', 'h3', 'h4'}

        def add(kind, label, xpath):
            if "'" in label or xpath in seen or (kind, label) in labels or len(places) >= MAX_ANCHORS:
                return
            if not tree.xpath(xpath):
                return
            seen.add(xpath)
            labels.add((kind, label))
            places.append((kind, f"{self._kind_label(kind)}: {label}", xpath))

        for node in tree.iter():
            if not isinstance(node.tag, str):
                continue
            if any(parent.get('t-foreach') for parent in node.iterancestors()) or node.get('t-foreach'):
                continue
            tag = node.tag
            for attribute in ('t-field', 't-out', 't-esc'):
                expression = node.get(attribute)
                if expression and "'" not in expression:
                    if attribute == 't-field':
                        add('field', self._field_label(expression, model_name, record_var),
                            f"//*[@{attribute}='{expression}']")
                    elif len(expression) <= 40 and '(' not in expression:
                        add('value', self._field_label(expression, model_name, record_var),
                            f"//*[@{attribute}='{expression}']")
            if tag in block_tags:
                for attribute in ('name', 'id'):
                    value = node.get(attribute)
                    if value and "'" not in value and (attribute == 'name' or tag in ('div', 'section', 'table')):
                        add('block', value.replace('_', ' ').replace('-', ' '), f"//{tag}[@{attribute}='{value}']")
            if tag in ('h1', 'h2', 'h3', 'h4'):
                text = ' '.join(''.join(node.itertext()).split())
                if text and len(text) <= 60:
                    add('title', text, f"//{tag}[normalize-space(.)='{text}']")
            if tag == 'th':
                text = ' '.join(''.join(node.itertext()).split())
                if text and len(text) <= 40:
                    add('column', text, f"//th[normalize-space(.)='{text}']")
        return places

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------
    @api.model
    def _ensure_places(self, view, model_name=None, record_var=None):
        """Create (or refresh) the places of ``view`` when needed."""
        view = view.sudo()
        if not view or view.type != 'qweb':
            return
        templates = self._collect_templates(view)
        parts = []
        for template in templates.sorted('id'):
            parts.extend(f"{v.id}:{v.arch_db or ''}" for v in self._template_views(template).sorted('id'))
        stamp = hashlib.md5('|'.join([f'v{PLACES_VERSION}'] + parts).encode()).hexdigest()
        existing = self.sudo().search([('view_id', '=', view.id)])
        if existing and all(
            (place.stamp, place.model_name or None, place.record_var or None)
            == (stamp, model_name or None, record_var or None)
            for place in existing
        ):
            return
        existing.unlink()
        # the same place (same label and path) of several templates is one place
        merged = {}
        for template in templates:
            for kind, name, xpath in self._extract_places(self._template_tree(template), model_name, record_var):
                merged.setdefault((kind, name, xpath), self.env['ir.ui.view'])
                merged[(kind, name, xpath)] |= template
        names = Counter(name for _kind, name, _xpath in merged)
        create_vals, shown = [], Counter()
        for index, ((kind, name, xpath), places_templates) in enumerate(merged.items()):
            shown[name] += 1
            if names[name] > 1 and shown[name] > 1:
                # same label but another path: tell them apart
                name = f"{name} ({places_templates[:1].key or places_templates[:1].name})"
            create_vals.append({
                'view_id': view.id, 'template_ids': [(6, 0, places_templates.ids)], 'sequence': index,
                'kind': kind, 'name': name, 'xpath': xpath, 'model_name': model_name,
                'record_var': record_var, 'stamp': stamp,
            })
        self.sudo().create(create_vals)

    @api.model
    def _prepare_from_context(self):
        view_id = self.env.context.get('ntw_view_id')
        if view_id:
            self._ensure_places(
                self.env['ir.ui.view'].browse(view_id),
                self.env.context.get('ntw_model') or None,
                self.env.context.get('ntw_var') or None,
            )

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        self._prepare_from_context()
        return super().name_search(name, domain, operator, limit)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        self._prepare_from_context()
        return super().web_search_read(domain, specification, offset=offset, limit=limit, order=order,
                                       count_limit=count_limit)
