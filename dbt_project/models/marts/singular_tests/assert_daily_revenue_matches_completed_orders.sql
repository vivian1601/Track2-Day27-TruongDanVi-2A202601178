-- A singular data test returns only failing rows. This reconciles the mart
-- against its completed-order source and catches join-driven revenue inflation.
with expected as (
    select
        order_date,
        count(*) as completed_order_rows,
        sum(amount_usd) as daily_revenue
    from {{ ref('stg_orders') }}
    where status = 'completed'
    group by 1
),
actual as (
    select
        order_date,
        completed_order_rows,
        daily_revenue
    from {{ ref('fct_daily_revenue') }}
)
select
    coalesce(actual.order_date, expected.order_date) as order_date,
    expected.completed_order_rows as expected_order_rows,
    actual.completed_order_rows as actual_order_rows,
    expected.daily_revenue as expected_revenue,
    actual.daily_revenue as actual_revenue
from actual
full outer join expected using (order_date)
where actual.order_date is null
   or expected.order_date is null
   or actual.completed_order_rows != expected.completed_order_rows
   or abs(actual.daily_revenue - expected.daily_revenue) > 0.000001
