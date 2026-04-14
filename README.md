# flamant-addons

Client-specific Odoo 18 Enterprise add-ons for Flamant Design.

## Modules

### `flamant_sales_report`

Consolidated POS + Sales reporting by channel / country / shop with monthly budget.

- Extends `crm.team` with `x_channel`, `x_country_code`, `x_shop_label`
- SQL-view model `flamant.daily.sales` — UNION of `pos.order` + `sale.order`, keyed on sales team
- Monthly budget model `flamant.shop.budget` (team × year × month)
- Pivot + list + graph views as the source for an Odoo Spreadsheet dashboard

Post-install hook auto-maps known team names (Brussels / Paris / Sint-Martens-Latem / Sint-Genesius-Rode / Wholesale / Website / …) to channel + country + shop label. Unmapped teams default to `Other`.

## Deploy to V18 demo (demobuddy)

```bash
ssh remote 'test -d /data/odoo-v18/addons/flamant-addons \
    || git clone https://github.com/snowtreebe/flamant-addons.git /data/odoo-v18/addons/flamant-addons'
ssh remote 'cd /data/odoo-v18/addons/flamant-addons && git pull'
ssh remote 'kubectl rollout restart deployment/odoo-v18 -n demos'
ssh remote 'kubectl rollout status deployment/odoo-v18 -n demos'
ssh remote 'kubectl exec -n demos deploy/odoo-v18 -- odoo -d demo-flamant \
    --stop-after-init -u flamant_sales_report -c /etc/odoo/odoo.conf'
```
