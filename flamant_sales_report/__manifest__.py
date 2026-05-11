{
    'name': 'Flamant KPI',
    'version': '18.0.4.0.0',
    'category': 'Sales/Sales',
    'summary': 'Consolidated POS + Sales KPI dashboard with channel / country / shop drilldown',
    'description': """
Flamant KPI
===========
Consolidates pos.order, sale.order, and customer invoices into a single
read-only SQL view (flamant.daily.sales) with two dedicated menu entries:

- **Invoiced Sales** — all rows with basis = invoiced
- **Order Intake**  — all rows with basis = order_intake
- **Quotations**    — open and cancelled sale.order records (draft, sent, cancel)

Each row carries a clickable Document link back to the originating POS
order, sales order, or invoice (source_ref + source_doc Reference field).

Dimensions available per row: date, channel, country, shop label, source.

Additionally extends crm.team with Flamant-specific reporting metadata
(channel, country, shop label, shop cluster, analytic account) and keeps
the legacy flamant.shop.budget and flamant.monthly.budget models for
future budget reporting (menus hidden pending budget v2).
""",
    'author': 'Digisolid',
    'website': 'https://digisolid.be',
    'depends': [
        'sales_team',
        'point_of_sale',
        'sale_management',
        'account_budget',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/crm_team_views.xml',
        'views/flamant_daily_sales_views.xml',
        'views/flamant_quotation_views.xml',
        'views/flamant_shop_budget_views.xml',
        'views/flamant_monthly_budget_views.xml',
        'views/menus.xml',
    ],
    'assets': {},
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
