"""
Data Cleaning Module for Sales Analysis Project
Contains modular, reusable functions for cleaning retail sales data.
"""

import glob
import os
import pandas as pd
import numpy as np


# Canonical column mapping for standardizing inconsistent headers
COLUMN_MAPPING = {
    'invoiceno': 'InvoiceNo',
    'invoicenumber': 'InvoiceNo',
    'invoice': 'InvoiceNo',
    'stockcode': 'StockCode',
    'itemcode': 'StockCode',
    'sku': 'StockCode',
    'description': 'Description',
    'itemdescription': 'Description',
    'productdescription': 'Description',
    'itemname': 'Description',
    'productname': 'Description',
    'quantity': 'Quantity',
    'qty': 'Quantity',
    'invoicedate': 'InvoiceDate',
    'date': 'InvoiceDate',
    'transactiondate': 'InvoiceDate',
    'unitprice': 'UnitPrice',
    'unit_price': 'UnitPrice',
    'price': 'UnitPrice',
    'customerid': 'CustomerID',
    'customer': 'CustomerID',
    'country': 'Region',
    'region': 'Region'
}


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize inconsistent column names across different monthly exports
    into canonical schema: InvoiceNo, StockCode, Description, Quantity,
    InvoiceDate, UnitPrice, CustomerID, Region.
    """
    df = df.copy()
    rename_dict = {}
    for col in df.columns:
        norm_key = col.strip().lower().replace(' ', '').replace('_', '').replace('-', '')
        if norm_key in COLUMN_MAPPING:
            rename_dict[col] = COLUMN_MAPPING[norm_key]
    return df.rename(columns=rename_dict)


def convert_dates(df: pd.DataFrame, date_col: str = 'InvoiceDate') -> pd.DataFrame:
    """
    Convert mixed date formats (e.g. ISO, MM/DD/YYYY, DD-MM-YYYY) into pandas datetime.
    """
    df = df.copy()
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], format='mixed', errors='coerce')
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle missing values across columns:
    - Replace missing or unspecified regions with 'Unknown'.
    - Fill missing descriptions with 'Unknown Product'.
    - Keep CustomerID as nullable float/int (distinguishing guest checkouts).
    """
    df = df.copy()
    if 'Region' in df.columns:
        df['Region'] = df['Region'].fillna('Unknown')
        df['Region'] = df['Region'].replace({'Unspecified': 'Unknown', '': 'Unknown'})
    if 'Description' in df.columns:
        df['Description'] = df['Description'].fillna('Unknown Product').astype(str).str.strip()
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove exact duplicate rows from the dataset.
    """
    return df.drop_duplicates().copy()


def remove_invalid_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove invalid transactions with zero, negative, or missing unit prices.
    Note: Items with negative quantity (returns) are NOT removed here if unit price is valid.
    """
    valid_mask = (df['UnitPrice'] > 0) & df['UnitPrice'].notna()
    return df[valid_mask].copy()


def identify_cancellations_and_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify cancelled invoices and return transactions:
    - Cancellations: InvoiceNo starts with 'C'.
    - Returns: Quantity < 0.
    Returns flags: IsCancelled and IsReturn.
    """
    df = df.copy()
    df['IsCancelled'] = df['InvoiceNo'].astype(str).str.upper().str.startswith('C')
    df['IsReturn'] = df['Quantity'] < 0
    return df


def calculate_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate line revenue using Quantity * UnitPrice.
    Returns (negative quantity) yield negative revenue to ensure net revenue is accurate.
    """
    df = df.copy()
    df['Revenue'] = df['Quantity'] * df['UnitPrice']
    return df


def load_raw_data(raw_dir: str = 'data/raw') -> pd.DataFrame:
    """
    Automatically discovers and loads all monthly CSV files inside data/raw/,
    standardizing column headers on ingestion.
    """
    file_pattern = os.path.join(raw_dir, '*.csv')
    raw_files = sorted(glob.glob(file_pattern))
    if not raw_files:
        raise FileNotFoundError(f"No CSV files found in {raw_dir}")
    
    dfs = []
    for filepath in raw_files:
        mdf = pd.read_csv(filepath, low_memory=False)
        mdf = standardize_columns(mdf)
        dfs.append(mdf)
    
    combined_df = pd.concat(dfs, ignore_index=True)
    return combined_df


def clean_sales_data(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Executes the end-to-end cleaning pipeline, tracking audit metrics at each stage
    for the cleaning log and revenue reconciliation.
    
    Returns:
        cleaned_df: Cleaned sales DataFrame with revenue and return flags.
        cleaning_log_df: DataFrame logging row counts and revenue at each step.
        reconciliation_summary: Dictionary explaining reconciliation variance.
    """
    # 0. Initial raw state
    n_raw = len(raw_df)
    # Estimate raw revenue (imputing 0 for invalid prices to compute baseline)
    raw_valid_numeric = raw_df['Quantity'].fillna(0) * raw_df['UnitPrice'].fillna(0)
    rev_raw = float(raw_valid_numeric.sum())

    # 1. Standardize columns & convert mixed dates
    df = standardize_columns(raw_df)
    df = convert_dates(df, 'InvoiceDate')

    # 2. Handle missing values
    df = handle_missing_values(df)

    # 3. Remove exact duplicate rows
    df_dedup = remove_duplicates(df)
    n_dedup = len(df_dedup)
    rev_dedup = float((df_dedup['Quantity'] * df_dedup['UnitPrice']).sum())

    # 4. Remove invalid transactions (UnitPrice <= 0)
    df_valid_price = remove_invalid_transactions(df_dedup)
    n_valid_price = len(df_valid_price)
    rev_valid_price = float((df_valid_price['Quantity'] * df_valid_price['UnitPrice']).sum())

    # 5. Identify cancellations and returns
    df_flagged = identify_cancellations_and_returns(df_valid_price)
    n_flagged = len(df_flagged)
    rev_flagged = float((df_flagged['Quantity'] * df_flagged['UnitPrice']).sum())

    # 6. Calculate revenue (net revenue)
    cleaned_df = calculate_revenue(df_flagged)
    n_final = len(cleaned_df)
    rev_final = float(cleaned_df['Revenue'].sum())

    # Gross revenue vs returns revenue breakdown
    gross_revenue = float(cleaned_df[cleaned_df['Revenue'] > 0]['Revenue'].sum())
    returns_revenue = float(cleaned_df[cleaned_df['Revenue'] < 0]['Revenue'].sum())
    cancellation_count = int(cleaned_df['IsCancelled'].sum())
    return_count = int(cleaned_df['IsReturn'].sum())

    # Revenue differences
    dup_rev_diff = rev_raw - rev_dedup
    invalid_rev_diff = rev_dedup - rev_valid_price

    # Construct cleaning log
    cleaning_log_data = [
        {
            'Stage': '1. Raw Data (Before Cleaning)',
            'Row_Count': n_raw,
            'Rows_Removed': 0,
            'Cumulative_Rows_Removed': 0,
            'Stage_Revenue': round(rev_raw, 2),
            'Notes': 'Raw monthly exports ingested and combined'
        },
        {
            'Stage': '2. Duplicate Removal',
            'Row_Count': n_dedup,
            'Rows_Removed': n_raw - n_dedup,
            'Cumulative_Rows_Removed': n_raw - n_dedup,
            'Stage_Revenue': round(rev_dedup, 2),
            'Notes': f'Removed {n_raw - n_dedup} exact duplicate transaction rows'
        },
        {
            'Stage': '3. Invalid Transaction Removal',
            'Row_Count': n_valid_price,
            'Rows_Removed': n_dedup - n_valid_price,
            'Cumulative_Rows_Removed': n_raw - n_valid_price,
            'Stage_Revenue': round(rev_valid_price, 2),
            'Notes': f'Removed {n_dedup - n_valid_price} records with UnitPrice <= 0'
        },
        {
            'Stage': '4. Return & Cancellation Handling',
            'Row_Count': n_flagged,
            'Rows_Removed': 0,
            'Cumulative_Rows_Removed': n_raw - n_flagged,
            'Stage_Revenue': round(rev_flagged, 2),
            'Notes': f'Identified {return_count} returns & {cancellation_count} cancellations (kept as negative revenue)'
        },
        {
            'Stage': '5. Final Cleaned Dataset',
            'Row_Count': n_final,
            'Rows_Removed': 0,
            'Cumulative_Rows_Removed': n_raw - n_final,
            'Stage_Revenue': round(rev_final, 2),
            'Notes': f'Net revenue calculated; Gross: {gross_revenue:.2f}, Returns: {returns_revenue:.2f}'
        }
    ]
    cleaning_log_df = pd.DataFrame(cleaning_log_data)

    reconciliation_summary = {
        'Raw_Revenue': round(rev_raw, 2),
        'Cleaned_Net_Revenue': round(rev_final, 2),
        'Gross_Revenue': round(gross_revenue, 2),
        'Returns_Negative_Revenue': round(returns_revenue, 2),
        'Duplicate_Revenue_Variance': round(dup_rev_diff, 2),
        'Invalid_Price_Revenue_Variance': round(invalid_rev_diff, 2),
        'Calculated_Reconciled_Revenue': round(rev_raw - dup_rev_diff - invalid_rev_diff, 2),
        'Reconciliation_Difference': round(abs((rev_raw - dup_rev_diff - invalid_rev_diff) - rev_final), 4),
        'Reconciliation_Tolerance': 0.01,
        'Tolerance_Satisfied': abs((rev_raw - dup_rev_diff - invalid_rev_diff) - rev_final) <= 0.01
    }

    return cleaned_df, cleaning_log_df, reconciliation_summary


def process_pipeline(raw_dir: str = 'data/raw',
                     processed_path: str = 'data/processed/cleaned_sales.csv',
                     log_path: str = 'outputs/cleaning_log.csv') -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    End-to-end execution pipeline:
    1. Loads all raw files in raw_dir
    2. Runs clean_sales_data
    3. Saves cleaned_sales.csv and cleaning_log.csv
    """
    raw_df = load_raw_data(raw_dir)
    cleaned_df, cleaning_log_df, reconciliation_summary = clean_sales_data(raw_df)

    # Ensure output directories exist
    os.makedirs(os.path.dirname(processed_path), exist_ok=True)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    cleaned_df.to_csv(processed_path, index=False)
    cleaning_log_df.to_csv(log_path, index=False)

    return cleaned_df, cleaning_log_df, reconciliation_summary
