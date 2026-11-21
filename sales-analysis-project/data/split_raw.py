import pandas as pd
import numpy as np
import os

df = pd.read_csv('sales-analysis-project/data/online_retail_raw.csv', encoding='latin1')
# Sample exactly 50,000 transactions reproducibly
sample_df = df.sample(n=50000, random_state=42).copy()
sample_df['InvoiceDate'] = pd.to_datetime(sample_df['InvoiceDate'])
sample_df = sample_df.sort_values('InvoiceDate').reset_index(drop=True)

# Group by year-month
sample_df['YearMonth'] = sample_df['InvoiceDate'].dt.to_period('M').astype(str)

column_variations = [
    # 2010-12
    {'InvoiceNo': 'InvoiceNo', 'StockCode': 'StockCode', 'Description': 'Description', 'Quantity': 'Quantity', 'InvoiceDate': 'InvoiceDate', 'UnitPrice': 'UnitPrice', 'CustomerID': 'CustomerID', 'Country': 'Country', 'date_fmt': '%m/%d/%Y %H:%M'},
    # 2011-01
    {'InvoiceNo': 'invoice_no', 'StockCode': 'stock_code', 'Description': 'description', 'Quantity': 'quantity', 'InvoiceDate': 'invoice_date', 'UnitPrice': 'unit_price', 'CustomerID': 'customer_id', 'Country': 'country', 'date_fmt': '%Y-%m-%d %H:%M:%S'},
    # 2011-02
    {'InvoiceNo': 'Invoice_No', 'StockCode': 'Stock_Code', 'Description': 'Description', 'Quantity': 'Qty', 'InvoiceDate': 'Invoice_Date', 'UnitPrice': 'Price', 'CustomerID': 'Customer_ID', 'Country': 'Region', 'date_fmt': '%d-%m-%Y %H:%M'},
    # 2011-03
    {'InvoiceNo': 'InvoiceNumber', 'StockCode': 'ItemCode', 'Description': 'Description', 'Quantity': 'Quantity', 'InvoiceDate': 'Date', 'UnitPrice': 'UnitPrice', 'CustomerID': 'CustomerID', 'Country': 'Country', 'date_fmt': '%Y/%m/%d %H:%M:%S'},
    # 2011-04
    {'InvoiceNo': 'InvoiceNo', 'StockCode': 'StockCode', 'Description': 'Product_Description', 'Quantity': 'Quantity', 'InvoiceDate': 'InvoiceDate', 'UnitPrice': 'Unit_Price', 'CustomerID': 'CustomerID', 'Country': 'Country', 'date_fmt': '%m/%d/%Y %H:%M'},
    # 2011-05
    {'InvoiceNo': 'Invoice', 'StockCode': 'StockCode', 'Description': 'Description', 'Quantity': 'Qty', 'InvoiceDate': 'InvoiceDate', 'UnitPrice': 'Price', 'CustomerID': 'CustomerID', 'Country': 'Region', 'date_fmt': '%Y-%m-%d %H:%M:%S'},
    # 2011-06
    {'InvoiceNo': 'INVOICENO', 'StockCode': 'STOCKCODE', 'Description': 'DESCRIPTION', 'Quantity': 'QUANTITY', 'InvoiceDate': 'INVOICEDATE', 'UnitPrice': 'UNITPRICE', 'CustomerID': 'CUSTOMERID', 'Country': 'COUNTRY', 'date_fmt': '%d/%m/%Y %H:%M'},
    # 2011-07
    {'InvoiceNo': 'invoice_number', 'StockCode': 'item_code', 'Description': 'description', 'Quantity': 'quantity', 'InvoiceDate': 'invoice_date', 'UnitPrice': 'unit_price', 'CustomerID': 'customer_id', 'Country': 'region', 'date_fmt': '%Y-%m-%d %H:%M:%S'},
    # 2011-08
    {'InvoiceNo': 'Invoice No', 'StockCode': 'Stock Code', 'Description': 'Description', 'Quantity': 'Quantity', 'InvoiceDate': 'Invoice Date', 'UnitPrice': 'Unit Price', 'CustomerID': 'Customer ID', 'Country': 'Region', 'date_fmt': '%m/%d/%Y %H:%M'},
    # 2011-09
    {'InvoiceNo': 'InvoiceNo', 'StockCode': 'SKU', 'Description': 'Item_Description', 'Quantity': 'Quantity', 'InvoiceDate': 'InvoiceDate', 'UnitPrice': 'UnitPrice', 'CustomerID': 'CustomerID', 'Country': 'Country', 'date_fmt': '%Y-%m-%d %H:%M:%S'},
    # 2011-10
    {'InvoiceNo': 'Invoice_Number', 'StockCode': 'StockCode', 'Description': 'Description', 'Quantity': 'Qty', 'InvoiceDate': 'Transaction_Date', 'UnitPrice': 'Price', 'CustomerID': 'Customer', 'Country': 'Region', 'date_fmt': '%d-%m-%Y %H:%M'},
    # 2011-11
    {'InvoiceNo': 'invoiceno', 'StockCode': 'stockcode', 'Description': 'description', 'Quantity': 'qty', 'InvoiceDate': 'invoicedate', 'UnitPrice': 'unitprice', 'CustomerID': 'customerid', 'Country': 'country', 'date_fmt': '%Y-%m-%d %H:%M:%S'},
    # 2011-12
    {'InvoiceNo': 'InvoiceNo', 'StockCode': 'StockCode', 'Description': 'Description', 'Quantity': 'Quantity', 'InvoiceDate': 'InvoiceDate', 'UnitPrice': 'UnitPrice', 'CustomerID': 'CustomerID', 'Country': 'Country', 'date_fmt': '%m/%d/%Y %H:%M'},
]

raw_dir = 'sales-analysis-project/data/raw'
os.makedirs(raw_dir, exist_ok=True)

months = sorted(sample_df['YearMonth'].unique())
print('Found months:', months)

total_exported = 0
for i, ym in enumerate(months):
    month_data = sample_df[sample_df['YearMonth'] == ym].copy()
    var = column_variations[i % len(column_variations)]
    
    # Introduce some missing Country/Region in a few files to test missing region cleaning
    if ym in ['2011-02', '2011-07', '2011-10']:
        mask = month_data.sample(frac=0.03, random_state=42).index
        month_data.loc[mask, 'Country'] = np.nan
        
    date_fmt = var['date_fmt']
    month_data['InvoiceDate'] = month_data['InvoiceDate'].dt.strftime(date_fmt)
    
    cols_rename = {k: v for k, v in var.items() if k != 'date_fmt'}
    month_data = month_data.drop(columns=['YearMonth']).rename(columns=cols_rename)
    
    fn = ym.replace('-', '_')
    filename = f'sales_{fn}.csv'
    filepath = os.path.join(raw_dir, filename)
    month_data.to_csv(filepath, index=False)
    print(f'Exported {filename}: {len(month_data)} rows, columns: {list(month_data.columns)[:4]}...')
    total_exported += len(month_data)

print('Total rows exported across monthly files:', total_exported)
