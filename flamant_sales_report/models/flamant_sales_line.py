from odoo import api, fields, models, tools


class FlamantSalesLine(models.Model):
    """Read-only line-level margin view across POS / Sale Order / Invoice.

    Cost is derived from stock.valuation.layer (AVCO at moment of delivery)
    where available, with a standard_price fallback for undelivered SO lines
    and manual invoices. Service products always have cost = 0.

    Three legs UNIONed:
      - POS line          → emits two rows (basis = order_intake AND invoiced)
      - Sale order line   → emits one row  (basis = order_intake), state in sale/done
      - Account move line → emits one row  (basis = invoiced), out_invoice/out_refund posted

    POS-invoiced account moves (pos.order.account_move set) are excluded from
    the invoice leg to prevent double-counting against the POS leg.

    See README #### Marge per Product report for the full design + examples.
    """

    _name = 'flamant.sales.line'
    _description = 'Flamant Margin per Product (line-level POS / SO / Invoice)'
    _auto = False
    _order = 'date desc'

    # --- Time dimensions ---
    date = fields.Date(readonly=True)
    year_num = fields.Integer(string='Year', readonly=True)
    month_num = fields.Integer(string='Month', readonly=True)
    weekday_num = fields.Selection(
        [
            ('1', 'Monday'), ('2', 'Tuesday'), ('3', 'Wednesday'),
            ('4', 'Thursday'), ('5', 'Friday'), ('6', 'Saturday'), ('7', 'Sunday'),
        ],
        string='Weekday',
        readonly=True,
    )

    # --- Basis ---
    basis = fields.Selection(
        [
            ('order_intake', 'Order Intake'),
            ('invoiced',     'Invoiced Sales'),
        ],
        readonly=True,
    )

    # --- Channel / country / shop (mirrors flamant.sales.header) ---
    team_id = fields.Many2one('crm.team', string='Sales Team', readonly=True)
    channel = fields.Selection(
        [
            ('shops',        'Shops'),
            ('ecommerce',    'Online / E-Commerce'),
            ('wholesale',    'Wholesale'),
            ('franchise',    'Franchise'),
            ('flamant_home', 'Flamant@Home'),
            ('outlet',       'Outlet'),
            ('other',        'Other'),
        ],
        readonly=True,
    )
    country_code = fields.Selection(
        [
            ('BE',    'Belgium'),
            ('FR',    'France'),
            ('INT',   'International'),
            ('OTHER', 'Other'),
        ],
        string='Country',
        readonly=True,
    )
    shop_label = fields.Char(readonly=True)
    shop_cluster = fields.Char(readonly=True)
    is_comparable = fields.Boolean(
        string='Comparable',
        readonly=True,
        help='Mirrors crm.team.comparable — flag for like-for-like comparisons.',
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Budget Analytic Account',
        readonly=True,
        help='Mirrors crm.team.analytic_account_id.',
    )

    # --- Source document ---
    source = fields.Selection(
        [
            ('pos',     'POS'),
            ('sale',    'Sale Order'),
            ('invoice', 'Customer Invoice'),
        ],
        readonly=True,
    )
    source_model = fields.Char(string='Source Model', readonly=True)
    source_id = fields.Integer(string='Source ID', readonly=True)
    source_ref = fields.Char(string='Reference', readonly=True)
    source_doc = fields.Reference(
        selection=[
            ('pos.order',    'POS Order'),
            ('sale.order',   'Sales Order'),
            ('account.move', 'Invoice'),
        ],
        string='Document',
        compute='_compute_source_doc',
    )

    # --- Product ---
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_categ_id = fields.Many2one('product.category', string='Category', readonly=True)

    # --- Quantities & money ---
    qty = fields.Float(string='Quantity', readonly=True)
    revenue = fields.Monetary(string='Revenue', readonly=True)
    cost = fields.Monetary(string='Cost', readonly=True)
    margin = fields.Monetary(string='Margin', readonly=True)
    margin_pct = fields.Float(string='Margin %', readonly=True, aggregator=None)
    cost_source = fields.Selection(
        [
            ('svl_actual',                'SVL Actual'),
            ('standard_price_fallback',   'Standard Price (fallback)'),
            ('none',                      'No Cost Data'),
        ],
        string='Cost Source',
        readonly=True,
    )

    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    @api.depends('source_model', 'source_id')
    def _compute_source_doc(self):
        for r in self:
            r.source_doc = (
                f"{r.source_model},{r.source_id}"
                if r.source_model and r.source_id else False
            )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY d.date, d.team_id, d.basis,
                                 d.source, d.source_id, d.product_id
                    ) AS id,
                    d.date,
                    EXTRACT(YEAR  FROM d.date)::int AS year_num,
                    EXTRACT(MONTH FROM d.date)::int AS month_num,
                    CASE EXTRACT(DOW FROM d.date)::int
                        WHEN 0 THEN '7' ELSE EXTRACT(DOW FROM d.date)::text
                    END AS weekday_num,
                    d.basis,
                    d.team_id,
                    t.channel                                                  AS channel,
                    CASE
                        WHEN t.channel IN ('ecommerce', 'wholesale') THEN
                            CASE
                                WHEN pc.code = 'BE' THEN 'BE'
                                WHEN pc.code = 'FR' THEN 'FR'
                                WHEN pc.code IS NOT NULL THEN 'INT'
                                ELSE 'OTHER'
                            END
                        ELSE t.country_code
                    END                                                          AS country_code,
                    COALESCE(NULLIF(t.shop_label, ''), t.name->>'en_US')       AS shop_label,
                    COALESCE(NULLIF(t.shop_cluster, ''), t.shop_label,
                             t.name->>'en_US')                                    AS shop_cluster,
                    COALESCE(t.comparable, FALSE)                                AS is_comparable,
                    t.analytic_account_id                                        AS analytic_account_id,
                    d.source,
                    d.source_model,
                    d.source_id,
                    d.source_ref,
                    d.product_id,
                    pt.categ_id                                                   AS product_categ_id,
                    d.qty,
                    d.revenue,
                    d.cost,
                    (d.revenue - d.cost)                                          AS margin,
                    CASE
                        WHEN d.revenue <> 0 THEN
                            ROUND(((d.revenue - d.cost) / d.revenue * 100)::numeric, 2)
                        ELSE 0
                    END                                                           AS margin_pct,
                    d.cost_source,
                    d.company_id,
                    rc.currency_id                                                AS currency_id
                FROM (
                    -- ========================================================
                    -- LEG 1a: POS lines → order_intake basis
                    -- ========================================================
                    SELECT
                        po.date_order::date                              AS date,
                        'order_intake'::varchar                          AS basis,
                        po.crm_team_id                                   AS team_id,
                        'pos'::varchar                                   AS source,
                        'pos.order'::varchar                             AS source_model,
                        po.id                                            AS source_id,
                        COALESCE(NULLIF(po.pos_reference, ''), po.name)  AS source_ref,
                        po.partner_id                                    AS partner_id,
                        po.company_id                                    AS company_id,
                        pol.product_id                                   AS product_id,
                        pol.qty                                          AS qty,
                        pol.price_subtotal                               AS revenue,
                        CASE
                            WHEN pt.type = 'service' THEN 0
                            ELSE COALESCE(
                                (SELECT -SUM(svl.value)
                                   FROM stock_valuation_layer svl
                                   JOIN stock_move sm     ON sm.id = svl.stock_move_id
                                   JOIN stock_picking sp  ON sp.id = sm.picking_id
                                  WHERE sp.pos_order_id = po.id
                                    AND sm.product_id = pol.product_id),
                                COALESCE((pp.standard_price ->> po.company_id::text)::numeric, 0) * pol.qty
                            )
                        END                                              AS cost,
                        CASE
                            WHEN pt.type = 'service' THEN 'none'
                            WHEN EXISTS (
                                SELECT 1
                                   FROM stock_valuation_layer svl
                                   JOIN stock_move sm     ON sm.id = svl.stock_move_id
                                   JOIN stock_picking sp  ON sp.id = sm.picking_id
                                  WHERE sp.pos_order_id = po.id
                                    AND sm.product_id = pol.product_id
                            ) THEN 'svl_actual'
                            ELSE 'standard_price_fallback'
                        END                                              AS cost_source
                    FROM pos_order_line pol
                    JOIN pos_order        po ON po.id = pol.order_id
                    JOIN product_product  pp ON pp.id = pol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    WHERE po.state NOT IN ('cancel', 'draft')
                      AND po.crm_team_id IS NOT NULL

                    UNION ALL

                    -- ========================================================
                    -- LEG 1b: POS lines → invoiced basis (cash sale counts as both)
                    -- ========================================================
                    SELECT
                        po.date_order::date,
                        'invoiced'::varchar,
                        po.crm_team_id,
                        'pos'::varchar,
                        'pos.order'::varchar,
                        po.id,
                        COALESCE(NULLIF(po.pos_reference, ''), po.name),
                        po.partner_id,
                        po.company_id,
                        pol.product_id,
                        pol.qty,
                        pol.price_subtotal,
                        CASE
                            WHEN pt.type = 'service' THEN 0
                            ELSE COALESCE(
                                (SELECT -SUM(svl.value)
                                   FROM stock_valuation_layer svl
                                   JOIN stock_move sm     ON sm.id = svl.stock_move_id
                                   JOIN stock_picking sp  ON sp.id = sm.picking_id
                                  WHERE sp.pos_order_id = po.id
                                    AND sm.product_id = pol.product_id),
                                COALESCE((pp.standard_price ->> po.company_id::text)::numeric, 0) * pol.qty
                            )
                        END,
                        CASE
                            WHEN pt.type = 'service' THEN 'none'
                            WHEN EXISTS (
                                SELECT 1
                                   FROM stock_valuation_layer svl
                                   JOIN stock_move sm     ON sm.id = svl.stock_move_id
                                   JOIN stock_picking sp  ON sp.id = sm.picking_id
                                  WHERE sp.pos_order_id = po.id
                                    AND sm.product_id = pol.product_id
                            ) THEN 'svl_actual'
                            ELSE 'standard_price_fallback'
                        END
                    FROM pos_order_line pol
                    JOIN pos_order        po ON po.id = pol.order_id
                    JOIN product_product  pp ON pp.id = pol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    WHERE po.state NOT IN ('cancel', 'draft')
                      AND po.crm_team_id IS NOT NULL

                    UNION ALL

                    -- ========================================================
                    -- LEG 2: Sale order lines → order_intake basis
                    --        Excludes downpayments + section/note lines.
                    -- ========================================================
                    SELECT
                        so.date_order::date,
                        'order_intake'::varchar,
                        so.team_id,
                        'sale'::varchar,
                        'sale.order'::varchar,
                        so.id,
                        so.name,
                        so.partner_shipping_id,
                        so.company_id,
                        sol.product_id,
                        sol.product_uom_qty,
                        sol.price_subtotal,
                        CASE
                            WHEN pt.type = 'service' THEN 0
                            ELSE COALESCE(
                                (SELECT -SUM(svl.value)
                                   FROM stock_valuation_layer svl
                                   JOIN stock_move sm ON sm.id = svl.stock_move_id
                                  WHERE sm.sale_line_id = sol.id),
                                COALESCE((pp.standard_price ->> so.company_id::text)::numeric, 0) * sol.product_uom_qty
                            )
                        END,
                        CASE
                            WHEN pt.type = 'service' THEN 'none'
                            WHEN EXISTS (
                                SELECT 1
                                   FROM stock_valuation_layer svl
                                   JOIN stock_move sm ON sm.id = svl.stock_move_id
                                  WHERE sm.sale_line_id = sol.id
                            ) THEN 'svl_actual'
                            ELSE 'standard_price_fallback'
                        END
                    FROM sale_order_line sol
                    JOIN sale_order       so ON so.id = sol.order_id
                    JOIN product_product  pp ON pp.id = sol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    WHERE so.state IN ('sale', 'done')
                      AND so.team_id IS NOT NULL
                      AND COALESCE(sol.is_downpayment, FALSE) = FALSE
                      AND (sol.display_type IS NULL
                           OR sol.display_type NOT IN ('line_section', 'line_note'))
                      AND sol.product_id IS NOT NULL

                    UNION ALL

                    -- ========================================================
                    -- LEG 3: Account move lines (invoices + refunds) → invoiced.
                    --        Skip POS-linked invoices (already in LEG 1b).
                    --        For out_refund, flip sign on qty / revenue / cost.
                    -- ========================================================
                    SELECT
                        am.invoice_date::date,
                        'invoiced'::varchar,
                        am.team_id,
                        'invoice'::varchar,
                        'account.move'::varchar,
                        am.id,
                        am.name,
                        am.partner_shipping_id,
                        am.company_id,
                        aml.product_id,
                        CASE WHEN am.move_type = 'out_refund'
                             THEN -aml.quantity
                             ELSE  aml.quantity
                        END,
                        CASE WHEN am.move_type = 'out_refund'
                             THEN -aml.price_subtotal
                             ELSE  aml.price_subtotal
                        END,
                        CASE
                            WHEN pt.type = 'service' THEN 0
                            ELSE (CASE WHEN am.move_type = 'out_refund' THEN -1 ELSE 1 END)
                                 * COALESCE(
                                     (SELECT -SUM(svl.value)
                                        FROM stock_valuation_layer svl
                                        JOIN stock_move sm ON sm.id = svl.stock_move_id
                                        JOIN sale_order_line_invoice_rel rel
                                             ON rel.order_line_id = sm.sale_line_id
                                       WHERE rel.invoice_line_id = aml.id),
                                     COALESCE((pp.standard_price ->> am.company_id::text)::numeric, 0) * aml.quantity
                                 )
                        END,
                        CASE
                            WHEN pt.type = 'service' THEN 'none'
                            WHEN EXISTS (
                                SELECT 1
                                   FROM stock_valuation_layer svl
                                   JOIN stock_move sm ON sm.id = svl.stock_move_id
                                   JOIN sale_order_line_invoice_rel rel
                                        ON rel.order_line_id = sm.sale_line_id
                                  WHERE rel.invoice_line_id = aml.id
                            ) THEN 'svl_actual'
                            ELSE 'standard_price_fallback'
                        END
                    FROM account_move_line aml
                    JOIN account_move      am ON am.id = aml.move_id
                    JOIN product_product   pp ON pp.id = aml.product_id
                    JOIN product_template  pt ON pt.id = pp.product_tmpl_id
                    WHERE am.state = 'posted'
                      AND am.move_type IN ('out_invoice', 'out_refund')
                      AND am.team_id IS NOT NULL
                      AND am.invoice_date IS NOT NULL
                      AND aml.display_type = 'product'
                      AND aml.product_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM pos_order po2 WHERE po2.account_move = am.id
                      )
                ) d
                LEFT JOIN crm_team        t  ON t.id  = d.team_id
                LEFT JOIN res_partner     p  ON p.id  = d.partner_id
                LEFT JOIN res_country     pc ON pc.id = p.country_id
                LEFT JOIN res_company     rc ON rc.id = d.company_id
                LEFT JOIN product_product pp ON pp.id = d.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
            )
            """
        )
