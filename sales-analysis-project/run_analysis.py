"""
Comprehensive Sales Analysis & Visualization Script
Executes all required analytical sections and generates deliverables:
- outputs/cleaning_log.csv
- outputs/cleaned_sales.csv and data/processed/cleaned_sales.csv
- outputs/monthly_revenue.csv
- outputs/product_ranking.csv
- outputs/regional_analysis.csv
- outputs/customer_segments.csv
- outputs/forecast_results.csv
- outputs/charts/ (6 charts)
"""

import os
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Import custom cleaning module
from src.cleaning import process_pipeline


def run_full_analysis():
    print("--- 1. Executing Data Cleaning Pipeline ---")
    raw_dir = 'data/raw'
    processed_path = 'data/processed/cleaned_sales.csv'
    log_path = 'outputs/cleaning_log.csv'

    cleaned_df, cleaning_log_df, recon = process_pipeline(
        raw_dir=raw_dir,
        processed_path=processed_path,
        log_path=log_path
    )
    # Also save copy in outputs for easy reference
    shutil.copy(processed_path, 'outputs/cleaned_sales.csv')

    print(f"Data cleaned successfully. Total valid rows: {len(cleaned_df):,}")
    print(f"Revenue Reconciliation Difference: £{recon['Reconciliation_Difference']:.2f}")

    # Ensure charts directory exists
    charts_dir = 'outputs/charts'
    os.makedirs(charts_dir, exist_ok=True)

    cleaned_df['InvoiceDate'] = pd.to_datetime(cleaned_df['InvoiceDate'])
    cleaned_df['YearMonth'] = cleaned_df['InvoiceDate'].dt.strftime('%Y-%m')

    # --- 2. Monthly Sales Analysis ---
    print("\n--- 2. Computing Monthly Analysis ---")
    monthly_df = cleaned_df.groupby('YearMonth').agg(
        Monthly_Revenue=('Revenue', 'sum'),
        Order_Count=('InvoiceNo', 'nunique')
    ).reset_index()
    monthly_df['Average_Order_Value'] = monthly_df['Monthly_Revenue'] / monthly_df['Order_Count']
    monthly_df['MoM_Growth_Pct'] = monthly_df['Monthly_Revenue'].pct_change() * 100

    monthly_df = monthly_df.rename(columns={'YearMonth': 'Month'})
    monthly_df = monthly_df.round({
        'Monthly_Revenue': 2,
        'Average_Order_Value': 2,
        'MoM_Growth_Pct': 2
    })
    monthly_df.to_csv('outputs/monthly_revenue.csv', index=False)
    print("Saved outputs/monthly_revenue.csv")

    # --- 3. Product Analysis ---
    print("\n--- 3. Computing Product Analysis ---")
    prod_summary = cleaned_df.groupby(['StockCode', 'Description']).agg(
        Revenue=('Revenue', 'sum'),
        Quantity_Sold=('Quantity', 'sum'),
        Order_Count=('InvoiceNo', 'nunique')
    ).reset_index()

    # Sort products by net revenue
    prod_ranked = prod_summary.sort_values('Revenue', ascending=False).reset_index(drop=True)
    prod_ranked['Rank'] = prod_ranked.index + 1

    # Classify Top 10, Bottom 10, and Standard
    n_products = len(prod_ranked)
    prod_ranked['Ranking_Category'] = 'Standard'
    prod_ranked.loc[:9, 'Ranking_Category'] = 'Top 10'
    prod_ranked.loc[n_products - 10:, 'Ranking_Category'] = 'Bottom 10'

    # Reorder columns
    prod_ranked = prod_ranked[['Rank', 'Ranking_Category', 'StockCode', 'Description', 'Revenue', 'Quantity_Sold', 'Order_Count']]
    prod_ranked = prod_ranked.round({'Revenue': 2})
    prod_ranked.to_csv('outputs/product_ranking.csv', index=False)
    print("Saved outputs/product_ranking.csv")

    top10_products = prod_ranked[prod_ranked['Ranking_Category'] == 'Top 10'].copy()
    bottom10_products = prod_ranked[prod_ranked['Ranking_Category'] == 'Bottom 10'].sort_values('Revenue', ascending=True).copy()

    # --- 4. Regional Analysis ---
    print("\n--- 4. Computing Regional Analysis ---")
    reg_summary = cleaned_df.groupby('Region').agg(
        Revenue=('Revenue', 'sum'),
        Order_Count=('InvoiceNo', 'nunique')
    ).reset_index()
    total_rev = reg_summary['Revenue'].sum()
    reg_summary['Revenue_Contribution_Pct'] = (reg_summary['Revenue'] / total_rev) * 100
    reg_summary = reg_summary.sort_values('Revenue', ascending=False).reset_index(drop=True)
    reg_summary = reg_summary.round({
        'Revenue': 2,
        'Revenue_Contribution_Pct': 2
    })
    reg_summary.to_csv('outputs/regional_analysis.csv', index=False)
    print("Saved outputs/regional_analysis.csv")

    # --- 5. Customer Segmentation (RFM) ---
    print("\n--- 5. Computing RFM Customer Segmentation ---")
    # Identify customers (drop null CustomerID)
    rfm_df = cleaned_df[cleaned_df['CustomerID'].notna()].copy()
    rfm_df['CustomerID'] = rfm_df['CustomerID'].astype(int)

    reference_date = rfm_df['InvoiceDate'].max() + pd.Timedelta(days=1)

    rfm = rfm_df.groupby('CustomerID').agg(
        Recency=('InvoiceDate', lambda x: (reference_date - x.max()).days),
        Frequency=('InvoiceNo', 'nunique'),
        Monetary=('Revenue', 'sum')
    ).reset_index()

    # Quintile scoring (1 to 5)
    rfm['R_Score'] = pd.qcut(rfm['Recency'].rank(method='first'), q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm['F_Score'] = pd.qcut(rfm['Frequency'].rank(method='first'), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm['M_Score'] = pd.qcut(rfm['Monetary'].rank(method='first'), q=5, labels=[1, 2, 3, 4, 5]).astype(int)

    def classify_segment(row):
        r = row['R_Score']
        f = row['F_Score']
        m = row['M_Score']
        fm_avg = (f + m) / 2.0
        if r >= 4 and fm_avg >= 4:
            return 'Champions'
        elif f >= 3 and r >= 3:
            return 'Loyal Customers'
        elif r >= 4 and f < 3:
            return 'Potential Loyalists'
        elif r <= 2 and (f >= 3 or m >= 3):
            return 'At Risk'
        else:
            return 'Others'

    rfm['Segment'] = rfm.apply(classify_segment, axis=1)

    total_customer_revenue = rfm['Monetary'].sum()
    seg_summary = rfm.groupby('Segment').agg(
        Customer_Count=('CustomerID', 'count'),
        Total_Revenue=('Monetary', 'sum'),
        Average_Revenue=('Monetary', 'mean'),
        Repeat_Purchase_Rate_Pct=('Frequency', lambda x: (x > 1).mean() * 100)
    ).reset_index()

    seg_summary['Revenue_Contribution_Pct'] = (seg_summary['Total_Revenue'] / total_customer_revenue) * 100

    # Sort logically
    segment_order = ['Champions', 'Loyal Customers', 'Potential Loyalists', 'At Risk', 'Others']
    seg_summary['Segment'] = pd.Categorical(seg_summary['Segment'], categories=segment_order, ordered=True)
    seg_summary = seg_summary.sort_values('Segment').reset_index(drop=True)

    seg_summary = seg_summary.round({
        'Total_Revenue': 2,
        'Average_Revenue': 2,
        'Repeat_Purchase_Rate_Pct': 2,
        'Revenue_Contribution_Pct': 2
    })
    seg_summary.to_csv('outputs/customer_segments.csv', index=False)
    print("Saved outputs/customer_segments.csv")

    # --- 6. Basic Revenue Forecasting (3-Month Moving Average) ---
    print("\n--- 6. Computing Revenue Forecast ---")
    monthly_series = monthly_df[['Month', 'Monthly_Revenue']].copy()
    n_months = len(monthly_series)

    # Holdout last 3 months for evaluation
    eval_window = 3
    train_df = monthly_series.iloc[:n_months - eval_window].copy()
    test_df = monthly_series.iloc[n_months - eval_window:].copy()

    # Predict test months using rolling 3 preceding months
    eval_records = []
    for idx in test_df.index:
        month_label = monthly_series.loc[idx, 'Month']
        actual_val = monthly_series.loc[idx, 'Monthly_Revenue']
        pred_val = monthly_series.loc[idx - 3:idx - 1, 'Monthly_Revenue'].mean()
        abs_err = abs(actual_val - pred_val)
        pct_err = (abs_err / actual_val) * 100
        eval_records.append({
            'Month': month_label,
            'Actual_Revenue': actual_val,
            'Predicted_Revenue': pred_val,
            'Absolute_Error': abs_err,
            'Percentage_Error_Pct': pct_err,
            'Forecast_Type': 'Holdout Evaluation'
        })

    eval_results_df = pd.DataFrame(eval_records)
    mape = eval_results_df['Percentage_Error_Pct'].mean()
    print(f"3-Month Holdout MAPE: {mape:.2f}%")

    # Future 3-month forecast
    future_months = ['2012-01', '2012-02', '2012-03']
    rev_history = list(monthly_series['Monthly_Revenue'].values)
    future_records = []
    for fm in future_months:
        pred_next = np.mean(rev_history[-3:])
        future_records.append({
            'Month': fm,
            'Actual_Revenue': np.nan,
            'Predicted_Revenue': pred_next,
            'Absolute_Error': np.nan,
            'Percentage_Error_Pct': np.nan,
            'Forecast_Type': 'Future Forecast'
        })
        rev_history.append(pred_next)

    future_forecast_df = pd.DataFrame(future_records)
    forecast_all_df = pd.concat([eval_results_df, future_forecast_df], ignore_index=True)
    forecast_all_df = forecast_all_df.round({
        'Actual_Revenue': 2,
        'Predicted_Revenue': 2,
        'Absolute_Error': 2,
        'Percentage_Error_Pct': 2
    })
    forecast_all_df.to_csv('outputs/forecast_results.csv', index=False)
    print("Saved outputs/forecast_results.csv")

    # --- 7. Matplotlib Visualizations (6 Charts) ---
    print("\n--- 7. Generating Visualizations ---")
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    plt.rcParams['font.sans-serif'] = 'Arial'
    plt.rcParams['axes.edgecolor'] = '#cccccc'
    plt.rcParams['axes.linewidth'] = 0.8

    # Chart 1: Monthly Revenue Trend
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    ax.plot(monthly_df['Month'], monthly_df['Monthly_Revenue'], marker='o', color='#1f77b4', linewidth=2.5, markersize=6)
    ax.set_title('Monthly Net Revenue Trend (Dec 2010 – Dec 2011)', fontsize=14, fontweight='bold', pad=12)
    ax.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax.set_ylabel('Net Revenue (£)', fontsize=11, fontweight='bold')
    ax.set_xticks(range(len(monthly_df['Month'])))
    ax.set_xticklabels(monthly_df['Month'], rotation=45, ha='right')
    ax.yaxis.set_major_formatter('£{x:,.0f}')
    for i, row in monthly_df.iterrows():
        ax.annotate(f"£{row['Monthly_Revenue']/1000:.1f}k",
                    (row['Month'], row['Monthly_Revenue']),
                    textcoords="offset points", xytext=(0, 8), ha='center', fontsize=8)
    plt.tight_layout()
    chart1_path = os.path.join(charts_dir, '01_monthly_revenue_trend.png')
    plt.savefig(chart1_path)
    plt.close()
    print(f"Generated {chart1_path}")

    # Chart 2: Top 10 Products
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    top10_sorted = top10_products.sort_values('Revenue', ascending=True)
    y_pos = range(len(top10_sorted))
    labels = [d[:32] + '...' if len(d) > 35 else d for d in top10_sorted['Description']]
    bars = ax.barh(y_pos, top10_sorted['Revenue'], color='#2ca02c', height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_title('Top 10 Products by Net Revenue', fontsize=14, fontweight='bold', pad=12)
    ax.set_xlabel('Total Revenue (£)', fontsize=11, fontweight='semibold')
    ax.xaxis.set_major_formatter('£{x:,.0f}')
    for bar in bars:
        width = bar.get_width()
        ax.annotate(f"£{width:,.0f}",
                    (width, bar.get_y() + bar.get_height() / 2),
                    textcoords="offset points", xytext=(6, 0), va='center', fontsize=8.5, fontweight='bold')
    ax.set_xlim(0, top10_sorted['Revenue'].max() * 1.15)
    plt.tight_layout()
    chart2_path = os.path.join(charts_dir, '02_top_10_products.png')
    plt.savefig(chart2_path)
    plt.close()
    print(f"Generated {chart2_path}")

    # Chart 3: Bottom 10 Products
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    bottom10_sorted = bottom10_products.sort_values('Revenue', ascending=False)
    y_pos = range(len(bottom10_sorted))
    labels_b = [d[:32] + '...' if len(d) > 35 else d for d in bottom10_sorted['Description']]
    bars = ax.barh(y_pos, bottom10_sorted['Revenue'], color='#d62728', height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels_b, fontsize=9)
    ax.set_title('Bottom 10 Products by Net Revenue (Fees & Returns Impact)', fontsize=14, fontweight='bold', pad=12)
    ax.set_xlabel('Total Revenue (£)', fontsize=11, fontweight='semibold')
    ax.xaxis.set_major_formatter('£{x:,.0f}')
    ax.axvline(0, color='black', linewidth=0.8, linestyle='--')
    for bar in bars:
        width = bar.get_width()
        ax.annotate(f"£{width:,.0f}",
                    (width, bar.get_y() + bar.get_height() / 2),
                    textcoords="offset points", xytext=(-8 if width < 0 else 6, 0),
                    va='center', ha='right' if width < 0 else 'left', fontsize=8.5, fontweight='bold')
    plt.tight_layout()
    chart3_path = os.path.join(charts_dir, '03_bottom_10_products.png')
    plt.savefig(chart3_path)
    plt.close()
    print(f"Generated {chart3_path}")

    # Chart 4: Regional Revenue Distribution
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    top_regions = reg_summary.head(6).copy()
    other_rev = reg_summary.iloc[6:]['Revenue'].sum()
    other_row = pd.DataFrame([{
        'Region': 'Other Countries',
        'Revenue': other_rev,
        'Revenue_Contribution_Pct': (other_rev / total_rev) * 100
    }])
    plot_regions = pd.concat([top_regions, other_row], ignore_index=True)
    bars = ax.bar(plot_regions['Region'], plot_regions['Revenue_Contribution_Pct'], color='#3b528b', width=0.55)
    ax.set_title('Regional Net Revenue Contribution (%)', fontsize=14, fontweight='bold', pad=12)
    ax.set_xlabel('Region / Market', fontsize=11, fontweight='bold')
    ax.set_ylabel('Revenue Contribution (%)', fontsize=11, fontweight='bold')
    ax.set_xticks(range(len(plot_regions['Region'])))
    ax.set_xticklabels(plot_regions['Region'], rotation=30, ha='right')
    ax.yaxis.set_major_formatter('{x:.0f}%')
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"{height:.1f}%",
                    (bar.get_x() + bar.get_width() / 2, height),
                    textcoords="offset points", xytext=(0, 4), ha='center', fontsize=9, fontweight='bold')
    ax.set_ylim(0, plot_regions['Revenue_Contribution_Pct'].max() * 1.15)
    plt.tight_layout()
    chart4_path = os.path.join(charts_dir, '04_regional_revenue_distribution.png')
    plt.savefig(chart4_path)
    plt.close()
    print(f"Generated {chart4_path}")

    # Chart 5: Customer Segment Revenue Contribution
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)
    colors = ['#2ca02c', '#1f77b4', '#17becf', '#ff7f0e', '#7f7f7f']
    
    # Donut / Pie
    wedges, texts, autotexts = ax1.pie(
        seg_summary['Revenue_Contribution_Pct'],
        labels=seg_summary['Segment'],
        autopct='%1.1f%%',
        startangle=140,
        colors=colors,
        pctdistance=0.8,
        textprops={'fontsize': 9}
    )
    plt.setp(autotexts, size=8.5, weight="bold")
    # Draw center circle for donut
    centre_circle = plt.Circle((0, 0), 0.60, fc='white')
    ax1.add_artist(centre_circle)
    ax1.set_title('Revenue Share by Segment (%)', fontsize=13, fontweight='bold')

    # Bar chart for Average Revenue per Customer
    bars = ax2.bar(seg_summary['Segment'], seg_summary['Average_Revenue'], color=colors, width=0.55)
    ax2.set_title('Average Revenue per Customer (£)', fontsize=13, fontweight='bold')
    ax2.set_ylabel('Avg Revenue (£)', fontsize=10, fontweight='bold')
    ax2.set_xticks(range(len(seg_summary['Segment'])))
    ax2.set_xticklabels(seg_summary['Segment'], rotation=35, ha='right')
    ax2.yaxis.set_major_formatter('£{x:,.0f}')
    for bar in bars:
        h = bar.get_height()
        ax2.annotate(f"£{h:,.0f}",
                     (bar.get_x() + bar.get_width() / 2, h),
                     textcoords="offset points", xytext=(0, 4), ha='center', fontsize=8.5, fontweight='bold')
    ax2.set_ylim(0, seg_summary['Average_Revenue'].max() * 1.15)
    plt.tight_layout()
    chart5_path = os.path.join(charts_dir, '05_customer_segment_revenue.png')
    plt.savefig(chart5_path)
    plt.close()
    print(f"Generated {chart5_path}")

    # Chart 6: Actual vs Predicted Revenue
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    all_months = list(monthly_df['Month']) + future_months
    actual_series = list(monthly_df['Monthly_Revenue']) + [np.nan]*3

    # Construct complete predicted timeline
    pred_series = [np.nan]*(n_months - eval_window) + list(eval_results_df['Predicted_Revenue']) + list(future_forecast_df['Predicted_Revenue'])

    ax.plot(all_months[:n_months], actual_series[:n_months], marker='o', color='#1f77b4', label='Actual Revenue', linewidth=2.2)
    # Plot predicted line
    ax.plot(all_months[n_months - eval_window - 1:n_months],
            [actual_series[n_months - eval_window - 1]] + list(eval_results_df['Predicted_Revenue']),
            marker='s', linestyle='--', color='#ff7f0e', label='Backtest Forecast (3-Mo Moving Avg)', linewidth=2.0)
    # Plot future forecast line
    future_x = [all_months[n_months - 1]] + future_months
    future_y = [actual_series[n_months - 1]] + list(future_forecast_df['Predicted_Revenue'])
    ax.plot(future_x, future_y, marker='^', linestyle=':', color='#2ca02c', label='Future 3-Month Forecast', linewidth=2.2)

    ax.axvspan(n_months - eval_window - 0.5, n_months - 0.5, color='#fff2cc', alpha=0.5, label='Holdout Evaluation Period')
    ax.axvspan(n_months - 0.5, len(all_months) - 0.5, color='#d9ead3', alpha=0.5, label='Future Forecast Horizon')

    ax.set_title('Actual vs Predicted Revenue (Evaluation & 3-Month Forecast)', fontsize=14, fontweight='bold', pad=12)
    ax.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax.set_ylabel('Net Revenue (£)', fontsize=11, fontweight='bold')
    ax.set_xticks(range(len(all_months)))
    ax.set_xticklabels(all_months, rotation=45, ha='right')
    ax.yaxis.set_major_formatter('£{x:,.0f}')
    ax.legend(loc='upper left', frameon=True, fontsize=9.5)
    plt.tight_layout()
    chart6_path = os.path.join(charts_dir, '06_actual_vs_predicted_revenue.png')
    plt.savefig(chart6_path)
    plt.close()
    print(f"Generated {chart6_path}")

    print("\n--- All Analysis Deliverables Generated Successfully! ---")


if __name__ == '__main__':
    run_full_analysis()
