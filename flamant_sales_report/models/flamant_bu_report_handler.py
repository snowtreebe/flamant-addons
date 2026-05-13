from odoo import models


class FlamantBuReportHandler(models.AbstractModel):
    """Custom engine for the BU report's Locked / Estimated budget columns.

    Each leaf-row expression carries the BU code in its `subformula`
    (e.g. "retail_be"). The engine returns ONE dict keyed by BU code,
    so the report runtime picks `result[expression.subformula]` for
    each expression. Parent rows use `engine='aggregation'` over leaves.
    """

    _name = 'flamant.bu.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Flamant BU Report Custom Handler'

    def _report_custom_engine_flamant_bu_locked(
        self, expressions, options, date_scope, current_groupby,
        next_groupby, offset=0, limit=None, warnings=None,
    ):
        return self._flamant_bu_budget_value(expressions, options, 'locked_amount')

    def _report_custom_engine_flamant_bu_estimated(
        self, expressions, options, date_scope, current_groupby,
        next_groupby, offset=0, limit=None, warnings=None,
    ):
        return self._flamant_bu_budget_value(expressions, options, 'estimated_amount')

    def _flamant_bu_budget_value(self, expressions, options, field_name):
        bu_codes = sorted({
            (expr.subformula or '').strip()
            for expr in expressions if (expr.subformula or '').strip()
        })
        # Pre-fill all keys to 0 so missing months render as 0.00 instead of None
        result = {bu: 0.0 for bu in bu_codes}

        if not bu_codes:
            return result

        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        domain = [
            ('business_unit', 'in', bu_codes),
            ('period_start', '>=', date_from),
            ('period_start', '<=', date_to),
        ]
        company_ids = [c.get('id') for c in (options.get('companies') or []) if c.get('id')]
        if company_ids:
            domain.append(('company_id', 'in', company_ids))

        for rec in self.env['flamant.bu.budget'].sudo().search(domain):
            result[rec.business_unit] += rec[field_name]

        return result
