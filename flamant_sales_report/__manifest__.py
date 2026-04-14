{
    'name': 'Flamant Sales Report',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Consolidated POS + Sales reporting by channel/country/shop with budget',
    'description': """
Flamant Sales Report
====================
- Extends crm.team with channel, country and shop label metadata
- Consolidates pos.order + sale.order into a single SQL view flamant.daily.sales
- Adds a monthly budget model per team (flamant.shop.budget)
- Pivot + list views as the source for the Odoo Spreadsheet dashboard
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
