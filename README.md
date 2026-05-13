# flamant-addons

Client-specific Odoo 18 Enterprise add-ons for Flamant Design.

## Modules

### `flamant_sales_report` — Flamant KPI

Consolidated POS + Sales reporting by channel / country / shop with monthly budget.

#### Operational data

- Extends `crm.team` with `x_channel`, `x_country_code`, `x_shop_label`, `x_shop_cluster`
- SQL view `flamant.daily.sales` — UNION of `pos.order` + `sale.order` + customer invoices,
  keyed on sales team
- Pivot + list + graph views feed the Orders menu (Quotations, Order Intake, Invoiced Sales)
- Post-install hook auto-maps known team names (Brussels / Paris / Sablon / Wholesale / …)
  to channel + country + shop label. Unmapped teams default to `Other`

#### Marge per Business Unit report

Native `account.report` instance under **Flamant KPI → Marge → Per Business Unit**.

- **Hierarchy**: Retail (BE/FR) · Ecommerce (BE/FR/INT) · Wholesale · Other (Outlet) · TOTAAL
- **Country logic** differs per channel:
  - Retail: `team.x_country_code` (where the shop physically is)
  - Ecommerce: `partner_shipping_id.country_id.code` (delivery country, INT = anything ≠ BE/FR)
- **Columns**: 6 Actuals (Omzet, Discount €, Discount %, COGS, Bruto Marge, % Bruto Marge)
  + 6 Budgets (Locked Budget, Δ Locked €/% , Estimated Budget, Δ Estimated €/%) — supercolumn
  header rendered via `custom_columns_subheaders`
- **Drilldowns** (click ▶ to expand):
  - Retail / Belgium → list of BE shops with omzet/cogs/marge per shop
  - Retail / France  → list of FR shops
  - Ecommerce / International → list of countries

#### Budget model

`flamant.bu.budget` — one row per (Business Unit × year × month), two free-edit
amount fields:

- `locked_amount` — set by the board (RvB)
- `estimated_amount` — rolling forecast, always overwritten with the latest value

Parent rows (Retail, Ecommerce, TOTAAL) are aggregated automatically from leaf rows.
Editable list under **Flamant KPI → Budget → Per Business Unit**.

#### Account tag mapping (user-configurable)

The Omzet / COGS / Discount columns scope themselves via **account.account.tag** records,
not hard-coded code prefixes. Three tags ship with the module:

| Tag              | Default seed (post-install hook)             |
|------------------|----------------------------------------------|
| Flamant Omzet    | All accounts where `code LIKE '70%'`         |
| Flamant COGS     | All accounts where `code LIKE '604%'`        |
| Flamant Discount | All accounts where `code LIKE '708%' / '709%'` |

End users adjust the scope themselves — no developer needed:

1. **Accounting → Configuration → Account Tags** — open any of the three tags to see
   which accounts are currently in scope, add/remove accounts here.
2. **Or** open a specific account form and edit the `Tags` field directly.
3. The report picks up the change on next refresh; no module upgrade required.

When new accounts are created later (e.g. a new 707x sub-account), they are **not**
auto-tagged. Either:

- tag them manually on creation, or
- re-run the backfill: from `odoo shell`,
  `from odoo.addons.flamant_sales_report.hooks import _flamant_tag_accounts; _flamant_tag_accounts(env)`

#### Menu structure (Flamant KPI)

```
Flamant KPI
├── Orders ▼
│   ├── Quotations
│   ├── Order Intake
│   └── Invoiced Sales
├── Marge ▼
│   └── Per Business Unit
└── Budget ▼
    └── Per Business Unit
```

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
