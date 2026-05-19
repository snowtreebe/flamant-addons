# flamant-addons

Client-specific Odoo 18 Enterprise add-ons for Flamant Design.

## Modules

### `flamant_sales_report` — Flamant KPI

Consolidated POS + Sales reporting by channel / country / shop with monthly budget.

#### Operational data

- Extends `crm.team` with `channel`, `country_code`, `shop_label`, `shop_cluster`,
  `comparable`, `analytic_account_id`
- SQL view `flamant.sales.header` — UNION of `pos.order` + `sale.order` + customer invoices,
  keyed on sales team (header-level: one row per source document × basis)
- SQL view `flamant.sales.line` — line-level counterpart with cost/margin per orderlijn
  (see "Order Intake Lines" section below)
- Pivot + list + graph views feed the Order Rapports menu (Quotations, Order Intake,
  Order Intake Lines, Invoiced Sales)
- Post-install hook auto-maps known team names (Brussels / Paris / Sablon / Wholesale / …)
  to channel + country + shop label. Unmapped teams default to `Other`

#### Marge per Business Unit report

Native `account.report` instance under **Flamant KPI → Marge → Per Business Unit**.

- **Hierarchy**: Retail (BE/FR) · Ecommerce (BE/FR/INT) · Wholesale · Other (Outlet) · TOTAAL
- **Country logic** differs per channel:
  - Retail: `team.country_code` (where the shop physically is)
  - Ecommerce: `partner_shipping_id.country_id.code` (delivery country, INT = anything ≠ BE/FR)
- **Columns**: 6 Actuals (Omzet, Discount €, Discount %, COGS, Bruto Marge, % Bruto Marge)
  + 6 Budgets (Locked Budget, Δ Locked €/% , Estimated Budget, Δ Estimated €/%) — supercolumn
  header rendered via `custom_columns_subheaders`
- **Drilldowns** (click ▶ to expand):
  - Retail / Belgium → list of BE shops with omzet/cogs/marge per shop
  - Retail / France  → list of FR shops
  - Ecommerce / International → list of countries

#### Order Intake Lines (line-level margin)

SQL view `flamant.sales.line` exposed as list/graph/pivot under **Flamant KPI → Order Rapports → Order Intake Lines**. Line-level counterpart to `Order Intake` (which is header-level on `flamant.sales.header`): one row per sale-line × basis, with **AVCO cost from `stock.valuation.layer`** (SVL) joined per outgoing move. Complements the GL-level Per Business Unit report (`account.move.line` + tagged accounts) which lives under Marge Rapports.

##### SQL view structure

```
flamant.sales.line  ←  UNION ALL of three legs:

  ┌─ leg 1: pos.order.line          → POS sales       (basis = order_intake AND invoiced)
  │           └─ via pos.order.picking_ids → stock.move → stock.valuation.layer
  │
  ├─ leg 2: sale.order.line         → confirmed SO    (basis = order_intake)
  │           └─ via sale_line_id → stock.move → stock.valuation.layer
  │           └─ fallback: product.product.standard_price × qty
  │
  └─ leg 3: account.move.line       → invoiced lines  (basis = invoiced)
            └─ via sale_line_ids → SOL → moves → SVL
            └─ fallback: product.product.standard_price × qty
            └─ skip if account_move.pos_order_ids set  (already in leg 1)
```

Each row is one (order-line × basis). Output columns: `date`, `basis`, `team_id`, `channel`, `country_code`, `shop_label`, `source`, `source_ref`, `product_id`, `product_categ_id`, `qty`, `revenue`, `cost`, `margin`, `margin_pct`, `cost_source`.

##### `cost_source` column

Tells the user where the cost figure came from:

| Value                       | Meaning                                                                 |
|-----------------------------|-------------------------------------------------------------------------|
| `svl_actual`                | Cost from `stock.valuation.layer` on the actual outgoing move (AVCO).   |
| `standard_price_fallback`   | No SVL yet (line not delivered, or no move link) → `qty × standard_price`. |
| `none`                      | Service product or no cost data → `cost = 0`, margin shows full revenue. |

Filter `cost_source = 'svl_actual'` in the pivot to see only fully-realised margins.

##### Edge cases handled

| Case                                          | Handling                                                                                       |
|-----------------------------------------------|------------------------------------------------------------------------------------------------|
| Downpayments (`is_downpayment = True`)        | Excluded.                                                                                      |
| Section / note lines                          | Excluded via `display_type NOT IN ('line_section','line_note')`.                              |
| Services on SO (transport, Bpost)             | `cost = 0`, `cost_source = 'none'`.                                                            |
| Gift Card POS                                 | `cost = 0`, `cost_source = 'none'`.                                                            |
| POS-invoiced via separate `account.move`      | Skipped in leg 3 when `am.pos_order_ids` is set — leg 1 (POS) is canonical, no double-count.   |
| Manual invoice (no SO, no POS)                | Cost = `qty × standard_price`, flagged `standard_price_fallback`.                              |
| Refund / credit note (`out_refund`)           | Negative `qty`, `revenue`, `cost` → net subtracts from totals; `margin_pct` stays positive.    |
| `standard_price = 0` on storable product      | Allowed — shows margin = 100% but `cost_source = 'standard_price_fallback'` flags it.          |
| Manual SVL revaluations (`stock_move_id NULL`)| Auto-excluded — joins only via move.                                                           |
| Customer returns (incoming moves)             | Not emitted by this view (not a sale event).                                                   |
| Multi-currency                                | Single-company EUR — no conversion needed.                                                     |

##### Worked examples

**1. Standard SO with delivery + invoice** — SO0500, 5× Vase @ €50 = €250. SVL on outgoing move: `qty=-5, unit_cost=22, value=-110`. → Two rows (intake + invoiced), both `cost=110, margin=140, 56%`, `cost_source=svl_actual`.

**2. SO confirmed, not yet delivered (fallback)** — SO0501, 3× Lantern @ €150 = €450, no SVL, `standard_price=60`. → One intake row `cost=180, margin=270, 60%`, `cost_source=standard_price_fallback`. Once delivered, the view automatically switches to `svl_actual`.

**3. SO with `standard_price=0` (the €208k risk category)** — SO0502, 2× ColorSample @ €80 = €160, no SVL, cost field empty. → `cost=0, margin=160, 100%`, `cost_source=standard_price_fallback`. The flag exposes the data-quality gap without hiding the order.

**4. POS cash sale** — POS Brussels/0123, 1× plaid @ €45, SVL on POS picking `qty=-1, unit_cost=11.04`. → Two rows (intake + invoiced), `cost=11.04, margin=33.96, 75.5%`, `cost_source=svl_actual`. POS always emits both bases.

**5. POS with service (Gift Card)** — POS Latem/0037, Gift Card @ €75, no picking. → Two rows, `cost=0, margin=75, 100%`, `cost_source=none`.

**6. POS invoiced via separate `account.move` (no double-count)** — POS Paris/0163 (€45 plaid) → VFRA/2026/00021 with `pos_order_ids=[Paris/0163]`. Leg 1 (POS) emits its two rows; **leg 3 skips this invoice** because `pos_order_ids` is set. Net: 2 rows total, not 4.

**7. Manual invoice (no SO, no POS)** — INV/2026/00200, 4× ProductX @ €100 = €400. No `sale_line_ids`, no `pos_order_ids`, `standard_price=35`. → One invoiced row `cost=140, margin=260, 65%`, `cost_source=standard_price_fallback`.

**8. Refund / credit note (`out_refund`)** — RINV/2026/00010, 2× Vase returned (Odoo stores `quantity=-2` on the AML). `standard_price=22`. → One invoiced row `qty=-2, revenue=-100, cost=-44, margin=-56`, `margin_pct=56%`. All negative bedragen, totals nettoteren correct.

**9. Service line on a mixed SO** — SO0505 has 3 product lines + 1 "Bpost Domestic" @ €4.12. The Bpost line shows up as its own row with `cost=0, margin=4.12, margin_pct=100, cost_source=none`. Filter `cost_source IN ('svl_actual','standard_price_fallback')` in the pivot to exclude transport from "real" product margin.

**10. Mixed SO (3 lines, 3 cost sources)** — SO0506 with Vase (delivered → `svl_actual`), Lantern (not delivered → `standard_price_fallback`), Bpost transport (service → `none`). Three intake rows, each with its own `cost_source`. Useful at line level; aggregated views can surface a "Mixed" indicator.

##### Recommended filters

- **"Echte" gerealiseerde marge** (managers): `basis = invoiced AND cost_source = svl_actual`.
- **Pipeline marge** (sales): `basis = order_intake` (any cost source — fallback is fine for indicative figures).
- **Data-quality check**: `cost_source = standard_price_fallback AND cost = 0` → flag products without cost.
- **Exclude transport/service noise**: `cost_source != 'none'`.
- **Like-for-like comparison**: `is_comparable = True` — only includes teams flagged
  as `comparable` on their `crm.team` form (same-store sales across periods).

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
├── Order Rapports ▼
│   ├── Quotations
│   ├── Order Intake               (header-level, flamant.sales.header)
│   ├── Order Intake Lines         (line-level, flamant.sales.line — incl. cost / margin)
│   └── Invoiced Sales
├── Marge Rapports ▼
│   └── Per Business Unit          (GL-level, account.report)
└── Budget ▼
    └── Per Business Unit
```

## Deploy to V18 demo (demobuddy)

### One-time setup

The host clones this repo to `/data/odoo-v18/addons/flamant-addons` (mounted in
the Odoo container as `/mnt/extra-addons/flamant-addons`). Because Odoo scans
only the direct subdirectories of each entry in `addons_path`, the **repo path
itself must be listed in `addons_path`** — same convention as `purchase-workflow`,
`server-ux`, `digisolid`, etc. In `/data/odoo-v18/config/odoo.conf`:

```
addons_path = …,/mnt/extra-addons/digisolid,/mnt/extra-addons/flamant-addons
```

Then `kubectl rollout restart deployment/odoo-v18 -n demos` to pick up the config.

### Update workflow

```bash
ssh remote 'test -d /data/odoo-v18/addons/flamant-addons \
    || git clone https://github.com/snowtreebe/flamant-addons.git /data/odoo-v18/addons/flamant-addons'
ssh remote 'cd /data/odoo-v18/addons/flamant-addons && git pull'
ssh remote 'kubectl exec -n demos deploy/odoo-v18 -- odoo -d demo-flamant \
    --stop-after-init -u flamant_sales_report -c /etc/odoo/odoo.conf'
```

(No file copy / sync step needed — Odoo loads directly from the repo path.)
