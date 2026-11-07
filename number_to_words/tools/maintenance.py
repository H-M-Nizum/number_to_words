# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

_logger = logging.getLogger(__name__)


def repoint_report_lines(env):
    """Place the report lines of every report rule again in the rule's report.

    A line is kept when a place with the same path exists in the report. Otherwise its place is
    cleared (the user chooses it again) and the generated change is removed, so nothing keeps
    silently pointing at another report.
    """
    Anchor = env['number.to.words.anchor']
    rules = env['number.to.words.rule'].with_context(active_test=False).search([('target', '=', 'report')])
    for rule in rules:
        Anchor._ensure_places(rule.report_view_id, rule.model_name, rule.record_var)
        broken = False
        for line in rule.line_ids.filtered(lambda l: l.target == 'report'):
            place = Anchor.search([
                ('view_id', '=', rule.report_view_id.id), ('xpath', '=', line.xpath_expr or False),
            ], limit=1) if line.xpath_expr else Anchor
            if place:
                line.report_anchor_id = place
            else:
                broken = True
                _logger.warning(
                    "Display rule %r: the place of a line is not part of the report %s any more, "
                    "choose it again.", rule.name, rule.report_view_id.key)
                env.cr.execute(
                    "UPDATE number_to_words_rule_line SET report_anchor_id = NULL, xpath_expr = NULL WHERE id = %s",
                    (line.id,))
        if broken:
            rule.invalidate_recordset()
            rule.with_context(active_test=False).report_view_ids.sudo().unlink()
        else:
            rule._refresh()


def ensure_default_systems(env):
    """Every language needs a numbering system: the first one when none is chosen yet."""
    for language in env['number.to.words.language'].with_context(active_test=False).search([('system_id', '=', False)]):
        if language.system_ids:
            language.system_id = language.system_ids.sorted(lambda system: (system.sequence, system.id))[0]
