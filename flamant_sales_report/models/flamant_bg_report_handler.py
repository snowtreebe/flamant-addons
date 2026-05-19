from odoo import models


class FlamantBgReportHandler(models.AbstractModel):
    """Handler for the GROUPED variant of the BU report.

    Inherits the leaf-budget engine from the flat handler and adds:
      - "Actuals | Budgets" supercolumn header
      - per-shop drilldown under Retail / Belgium and Retail / France
      - per-country drilldown under Ecommerce / International
      - Discount columns (uses Flamant Discount account tag)
    """

    _name = 'flamant.bg.report.handler'
    _inherit = 'flamant.bu.report.handler'
    _description = 'Flamant BU Report Custom Handler (Grouped Header)'

    _DRILLDOWN_FUNCTIONS = {
        'FLM_BU_RETAIL_BE': '_report_expand_unfoldable_line_flamant_bu_retail_shops',
        'FLM_BU_RETAIL_FR': '_report_expand_unfoldable_line_flamant_bu_retail_shops',
        'FLM_BU_ECOM_INT':  '_report_expand_unfoldable_line_flamant_bu_ecom_intl_countries',
    }

    LOCKED_BUDGET_LABELS = {'locked_budget', 'delta_locked_eur', 'delta_locked_pct'}
    ESTIMATED_BUDGET_LABELS = {'estimated_budget', 'delta_estimated_eur', 'delta_estimated_pct'}

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        prev = previous_options or {}
        show_locked = prev.get('flamant_show_locked', True)
        show_estimated = prev.get('flamant_show_estimated', True)
        options['flamant_show_locked'] = show_locked
        options['flamant_show_estimated'] = show_estimated
        # Drop the hidden budget columns so the report renders
        # without them. Aggregation expressions still evaluate but
        # never reach the UI.
        options['columns'] = [
            col for col in options['columns']
            if (show_locked or col.get('expression_label') not in self.LOCKED_BUDGET_LABELS)
            and (show_estimated or col.get('expression_label') not in self.ESTIMATED_BUDGET_LABELS)
        ]
        # Build supercolumn subheaders matching the visible columns.
        subheaders = [{'name': 'Actuals', 'colspan': 6}]
        budgets_span = (3 if show_locked else 0) + (3 if show_estimated else 0)
        if budgets_span:
            subheaders.append({'name': 'Budgets', 'colspan': budgets_span})
        options['custom_columns_subheaders'] = subheaders
        options['ignore_totals_below_sections'] = True

    # ----- helpers ----- #

    def _flamant_drilldown_values(self, omzet, cogs, discount):
        marge = omzet - cogs
        pct = (100.0 * marge / omzet) if omzet else 0.0
        gross = omzet + discount
        discount_pct = (100.0 * discount / gross) if gross else 0.0
        return {
            'omzet': omzet,
            'discount_eur': discount,
            'discount_pct': discount_pct,
            'cogs': cogs,
            'marge': marge,
            'pct': pct,
            'locked_budget': 0.0,
            'delta_locked_eur': omzet,
            'delta_locked_pct': 0.0,
            'estimated_budget': 0.0,
            'delta_estimated_eur': omzet,
            'delta_estimated_pct': 0.0,
        }

    def _flamant_drilldown_columns(self, report, options, values):
        return [
            report._build_column_dict(values.get(col.get('expression_label'), 0.0), col, options=options)
            for col in options['columns']
        ]

    def _flamant_tag_account_ids(self, tag_name):
        return self.env['account.account'].sudo().search(
            [('tag_ids.name', '=', tag_name)]
        ).ids

    # ----- postprocess ----- #

    def _custom_line_postprocessor(self, report, options, lines):
        """Mark our 3 drilldown lines as unfoldable + register their expand
        function, and — when "Allemaal uitvouwen" is on — also inject the
        expanded child rows here.

        Reason: Odoo's `_fully_unfold_lines_if_needed` batch runs BEFORE the
        custom postprocessor, and sets `expand_function=None` for any line
        without a static `groupby`.  That makes the framework skip our 3
        drilldowns on unfold-all.  We do the expansion ourselves so the
        result is identical to manually clicking each row.
        """
        lines = super()._custom_line_postprocessor(report, options, lines)
        unfold_all = bool(options.get('unfold_all'))

        result = []
        for line in lines:
            result.append(line)

            try:
                model, line_id = report._get_model_info_from_id(line['id'])
            except Exception:
                continue
            if model != 'account.report.line':
                continue
            rline = self.env['account.report.line'].browse(line_id)
            fn_name = self._DRILLDOWN_FUNCTIONS.get(rline.code)
            if not fn_name:
                continue

            line['unfoldable'] = True
            line['expand_function'] = fn_name

            if not unfold_all:
                continue

            # Skip if children are already in the buffer (manual unfold or a
            # prior pass already injected them).
            already_expanded = any(
                l.get('parent_id') == line['id'] for l in lines
            )
            if already_expanded:
                line['unfolded'] = True
                continue

            line['unfolded'] = True
            expansion = getattr(self, fn_name)(
                line['id'], None, options, None, 0,
            )
            for child in expansion.get('lines', []):
                result.append(child)
        return result

    # ----- retail shops drilldown ----- #

    def _report_expand_unfoldable_line_flamant_bu_retail_shops(
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
        country = 'BE' if parent_line.code == 'FLM_BU_RETAIL_BE' else 'FR'

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
        disc_acc_ids = self._flamant_tag_account_ids('Flamant Discount')

        Aml = self.env['account.move.line'].sudo()
        base = [
            ('team_id', 'in', teams.ids),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('parent_state', '=', 'posted'),
        ]

        def _sum_by_team(account_ids, negate=False):
            if not account_ids:
                return {}
            groups = Aml._read_group(
                base + [('account_id', 'in', account_ids)],
                groupby=['team_id'], aggregates=['balance:sum'],
            )
            sign = -1 if negate else 1
            return {team.id: sign * bal for team, bal in groups}

        omzet_by_team = _sum_by_team(omzet_acc_ids, negate=True)
        cogs_by_team = _sum_by_team(cogs_acc_ids, negate=False)
        disc_by_team = _sum_by_team(disc_acc_ids, negate=False)

        child_level = (parent_line.hierarchy_level or 1) + 1
        lines = []
        for team in teams:
            omzet = omzet_by_team.get(team.id, 0.0)
            cogs = cogs_by_team.get(team.id, 0.0)
            discount = disc_by_team.get(team.id, 0.0)
            values = self._flamant_drilldown_values(omzet, cogs, discount)
            columns = self._flamant_drilldown_columns(report, options, values)

            team_label = team.shop_label or team.name
            if isinstance(team_label, dict):
                team_label = team_label.get('en_US') or next(iter(team_label.values()), '')

            lines.append({
                'id': report._get_generic_line_id('crm.team', team.id, parent_line_id=line_dict_id),
                'name': team_label or f'Team #{team.id}',
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

    # ----- ecommerce international drilldown ----- #

    def _report_expand_unfoldable_line_flamant_bu_ecom_intl_countries(
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
        if parent_line.code != 'FLM_BU_ECOM_INT':
            return empty

        date_from = options['date']['date_from']
        date_to = options['date']['date_to']

        omzet_acc_ids = self._flamant_tag_account_ids('Flamant Omzet')
        cogs_acc_ids = self._flamant_tag_account_ids('Flamant COGS')
        disc_acc_ids = self._flamant_tag_account_ids('Flamant Discount')

        tag_to_accs = {
            'omzet': tuple(omzet_acc_ids),
            'cogs': tuple(cogs_acc_ids),
            'discount': tuple(disc_acc_ids),
        }
        # Pre-build the IN clauses as parameters; psycopg expects sequences
        # to be tuples. Empty tuple is invalid in SQL, so we skip in code.

        all_acc_ids = tuple(set(omzet_acc_ids + cogs_acc_ids + disc_acc_ids))
        if not all_acc_ids:
            return empty

        self.env.cr.execute(
            """
            SELECT
                c.id AS country_id,
                SUM(CASE WHEN aml.account_id = ANY(%s) THEN -aml.balance ELSE 0 END) AS omzet,
                SUM(CASE WHEN aml.account_id = ANY(%s) THEN  aml.balance ELSE 0 END) AS cogs,
                SUM(CASE WHEN aml.account_id = ANY(%s) THEN  aml.balance ELSE 0 END) AS discount
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
            (list(omzet_acc_ids), list(cogs_acc_ids), list(disc_acc_ids),
             list(all_acc_ids), date_from, date_to),
        )
        rows = self.env.cr.fetchall()
        rows.sort(key=lambda r: -(float(r[1] or 0.0)))

        Country = self.env['res.country']
        child_level = (parent_line.hierarchy_level or 1) + 1
        lines = []
        for country_id, omzet, cogs, discount in rows:
            omzet = float(omzet or 0.0)
            cogs = float(cogs or 0.0)
            discount = float(discount or 0.0)
            if omzet == 0 and cogs == 0 and discount == 0:
                continue
            country = Country.browse(country_id) if country_id else Country
            name = (country.name if country else None) or '(Onbekend land)'

            values = self._flamant_drilldown_values(omzet, cogs, discount)
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
