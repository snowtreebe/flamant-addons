from odoo import models


class FlamantPjReportHandler(models.AbstractModel):
    """Handler for the 'Marge per Business Unit PJ' variant.

    Same lines / drilldown as the BG variant, but the column set drops
    the Discount columns and adds three new ones: Other Operating Income,
    Total Margin (eur), Total Margin (%). Subheader colspan is 7|6.

    OOI is sourced from accounts tagged 'Flamant Other Operating Income'
    (default seed: 700900 'Freight Costs Recharged to Customer'). Total
    margin = gross margin + OOI; total margin % = total_margin / turnover.
    """

    _name = 'flamant.pj.report.handler'
    _inherit = 'flamant.bg.report.handler'
    _description = 'Flamant BU Report Custom Handler (PJ variant)'

    def _custom_options_initializer(self, report, options, previous_options=None):
        # Let the BG handler do all the work (budget toggles, column
        # filtering, ignore_totals_below_sections), then override the
        # Actuals colspan since PJ has 7 actual cols (Turnover, COGS,
        # Gross Margin, GM %, OOI, Total Margin EUR, Total Margin %).
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        show_locked = options.get('flamant_show_locked', True)
        show_estimated = options.get('flamant_show_estimated', True)
        subheaders = [{'name': 'Actuals', 'colspan': 7}]
        budgets_span = (3 if show_locked else 0) + (3 if show_estimated else 0)
        if budgets_span:
            subheaders.append({'name': 'Budgets', 'colspan': budgets_span})
        options['custom_columns_subheaders'] = subheaders

    _DRILLDOWN_FUNCTIONS = {
        'FLM_PJ_RETAIL_BE': '_report_expand_unfoldable_line_flamant_pj_retail_shops',
        'FLM_PJ_RETAIL_FR': '_report_expand_unfoldable_line_flamant_pj_retail_shops',
        'FLM_PJ_ECOM_INT':  '_report_expand_unfoldable_line_flamant_pj_ecom_intl_countries',
    }

    def _flamant_pj_drilldown_values(self, omzet, cogs, ooi):
        marge = omzet - cogs
        pct = (100.0 * marge / omzet) if omzet else 0.0
        total_margin = marge + ooi
        total_margin_pct = (100.0 * total_margin / omzet) if omzet else 0.0
        return {
            'omzet': omzet,
            'cogs': cogs,
            'marge': marge,
            'pct': pct,
            'ooi': ooi,
            'total_margin_eur': total_margin,
            'total_margin_pct': total_margin_pct,
            'locked_budget': 0.0,
            'delta_locked_eur': omzet,
            'delta_locked_pct': 0.0,
            'estimated_budget': 0.0,
            'delta_estimated_eur': omzet,
            'delta_estimated_pct': 0.0,
        }

    def _report_expand_unfoldable_line_flamant_pj_retail_shops(
        self, line_dict_id, groupby, options, progress, offset,
        unfold_all_batch_data=None,
    ):
        report = self.env['account.report'].browse(options['report_id'])
        empty = {'lines': [], 'offset_increment': 0, 'has_more': False, 'progress': progress or {}}
        try:
            model, line_id = report._get_model_info_from_id(line_dict_id)
        except Exception:
            return empty
        if model != 'account.report.line':
            return empty
        parent_line = self.env['account.report.line'].browse(line_id)
        country = 'BE' if parent_line.code == 'FLM_PJ_RETAIL_BE' else 'FR'

        teams = self.env['crm.team'].search([
            ('channel', '=', 'shops'),
            ('country_code', '=', country),
        ], order='name')
        if not teams:
            return empty

        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        omzet_acc_ids = self._flamant_tag_account_ids('Flamant Omzet')
        cogs_acc_ids = self._flamant_tag_account_ids('Flamant COGS')
        ooi_acc_ids = self._flamant_tag_account_ids('Flamant Other Operating Income')

        Aml = self.env['account.move.line'].sudo()
        base = [
            ('team_id', 'in', teams.ids),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('parent_state', '=', 'posted'),
        ]

        def _by(ids, neg=False):
            if not ids:
                return {}
            groups = Aml._read_group(
                base + [('account_id', 'in', ids)],
                groupby=['team_id'], aggregates=['balance:sum'],
            )
            sign = -1 if neg else 1
            return {t.id: sign * b for t, b in groups}

        omzet_by = _by(omzet_acc_ids, neg=True)
        cogs_by = _by(cogs_acc_ids, neg=False)
        ooi_by = _by(ooi_acc_ids, neg=True)

        child_level = (parent_line.hierarchy_level or 1) + 1
        lines = []
        for team in teams:
            omzet = omzet_by.get(team.id, 0.0)
            cogs = cogs_by.get(team.id, 0.0)
            ooi = ooi_by.get(team.id, 0.0)
            values = self._flamant_pj_drilldown_values(omzet, cogs, ooi)
            columns = self._flamant_drilldown_columns(report, options, values)

            label = team.shop_label or team.name
            if isinstance(label, dict):
                label = label.get('en_US') or next(iter(label.values()), '')

            lines.append({
                'id': report._get_generic_line_id('crm.team', team.id, parent_line_id=line_dict_id),
                'name': label or f'Team #{team.id}',
                'columns': columns,
                'level': child_level,
                'parent_id': line_dict_id,
                'unfoldable': False,
                'unfolded': False,
                'caret_options': None,
            })

        return {
            'lines': lines,
            'offset_increment': len(lines),
            'has_more': False,
            'progress': progress or {},
        }

    def _report_expand_unfoldable_line_flamant_pj_ecom_intl_countries(
        self, line_dict_id, groupby, options, progress, offset,
        unfold_all_batch_data=None,
    ):
        report = self.env['account.report'].browse(options['report_id'])
        empty = {'lines': [], 'offset_increment': 0, 'has_more': False, 'progress': progress or {}}
        try:
            model, line_id = report._get_model_info_from_id(line_dict_id)
        except Exception:
            return empty
        if model != 'account.report.line':
            return empty
        parent_line = self.env['account.report.line'].browse(line_id)
        if parent_line.code != 'FLM_PJ_ECOM_INT':
            return empty

        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        omzet_acc_ids = self._flamant_tag_account_ids('Flamant Omzet')
        cogs_acc_ids = self._flamant_tag_account_ids('Flamant COGS')
        ooi_acc_ids = self._flamant_tag_account_ids('Flamant Other Operating Income')
        all_acc_ids = tuple(set(omzet_acc_ids + cogs_acc_ids + ooi_acc_ids))
        if not all_acc_ids:
            return empty

        self.env.cr.execute(
            """
            SELECT
                c.id AS country_id,
                SUM(CASE WHEN aml.account_id = ANY(%s) THEN -aml.balance ELSE 0 END) AS omzet,
                SUM(CASE WHEN aml.account_id = ANY(%s) THEN  aml.balance ELSE 0 END) AS cogs,
                SUM(CASE WHEN aml.account_id = ANY(%s) THEN -aml.balance ELSE 0 END) AS ooi
            FROM account_move_line aml
            JOIN account_move      am   ON am.id   = aml.move_id
            JOIN crm_team          t    ON t.id    = am.team_id
            LEFT JOIN res_partner  ship ON ship.id = am.partner_shipping_id
            LEFT JOIN res_country  c    ON c.id    = ship.country_id
            WHERE t.channel = 'ecommerce'
              AND aml.account_id = ANY(%s)
              AND COALESCE(c.code, 'XX') NOT IN ('BE', 'FR')
              AND aml.date BETWEEN %s AND %s
              AND aml.parent_state = 'posted'
            GROUP BY c.id
            """,
            (list(omzet_acc_ids), list(cogs_acc_ids), list(ooi_acc_ids),
             list(all_acc_ids), date_from, date_to),
        )
        rows = self.env.cr.fetchall()
        rows.sort(key=lambda r: -(float(r[1] or 0.0)))

        Country = self.env['res.country']
        child_level = (parent_line.hierarchy_level or 1) + 1
        lines = []
        for country_id, omzet, cogs, ooi in rows:
            omzet = float(omzet or 0.0)
            cogs = float(cogs or 0.0)
            ooi = float(ooi or 0.0)
            if omzet == 0 and cogs == 0 and ooi == 0:
                continue
            country = Country.browse(country_id) if country_id else Country
            name = (country.name if country else None) or '(Onbekend land)'

            values = self._flamant_pj_drilldown_values(omzet, cogs, ooi)
            columns = self._flamant_drilldown_columns(report, options, values)

            line_id_str = (
                report._get_generic_line_id('res.country', country.id, parent_line_id=line_dict_id)
                if country
                else report._get_generic_line_id('res.country', None, markup='unknown', parent_line_id=line_dict_id)
            )

            lines.append({
                'id': line_id_str,
                'name': name,
                'columns': columns,
                'level': child_level,
                'parent_id': line_dict_id,
                'unfoldable': False,
                'unfolded': False,
                'caret_options': None,
            })

        return {
            'lines': lines,
            'offset_increment': len(lines),
            'has_more': False,
            'progress': progress or {},
        }
