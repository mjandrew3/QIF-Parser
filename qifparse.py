# -*- coding: utf-8 -*-
"""This script aims to take a .QIF Quicken file as an import.  It will
then process the file and create separate flat files based on the section
from the QIF file.  

The currently supported sections are:
Tags
Category
Account
Transaction
Investment
Memorized
Security
Prices
"""


import datetime
import re

import numpy as np
import pandas as pd

from utils import fix_price,parse_cat,parse_acct,parse_tran,parse_inv


non_invst_account_types = [
    '!Type:Cash ',
    '!Type:Bank ',
    '!Type:CCard',
    '!Type:Oth A',
    '!Type:Oth L']

#Import QIF datafile
data = open("Quicken Data.QIF",'r').read()
chunks = data.split('\n^\n')


#Set up lists to handle and process outputs
type_list = []
type_list_index = []
tag_list = []
security_list = []
price_list = []
category_list = []
account_list = []
transaction_list = []
investment_list = []
memorized_list = []
counter = 0

for chunk in chunks:
    if not chunk:
        continue
    chunk = chunk.replace('!Option:AutoSwitch\n','').replace('!Clear:AutoSwitch\n','')
    first_line = chunk.split('\n')[0]
    if first_line == '!Type:Tag':
        last_type = 'tag'
        tag_list.append(chunk.split('\n')[1][1:])
    elif first_line == '!Type:Cat':
        category_list.append(parse_cat(chunk.split('\n')[1:]))
        last_type = 'category'
    elif first_line == '!Account':
        last_type = 'account'
        account_list.append(parse_acct(chunk.split('\n')[1:]))
        account = parse_acct(chunk.split('\n')[1:])[0]
    elif first_line in non_invst_account_types:
        last_type = 'transaction'
        transaction_list.append(parse_tran(counter,account,chunk.split('\n')[1:])[0])
    elif first_line == '!Type:Invst':
        last_type = 'investment'
        investment_list.append(parse_inv(counter,account,chunk.split('\n')[1:]))
    elif first_line == '!Type:Memorized':
        last_type = 'memorized'
        transactions_header = first_line
    elif first_line == '!Type:Security':
        last_type = 'security'
        temp_list = chunk.split('\n')
        sec_ticker = ''
        for line in temp_list:
            if line[0] == 'N':
                #Security Name
                sec_name = re.sub(' +',' ',line[1:])
            if line[0] == 'T':
                #Security Type
                sec_type = line[1:]
            if line[0] == 'S':
                #Security Ticker
                sec_ticker = line[1:]
        security_list.append([sec_name,sec_type,sec_ticker])
    elif first_line == '!Type:Prices':
        temp_list = chunk.split('\n')[1].split(',')
        price_list.append([temp_list[0].replace('"',''),
                           fix_price(temp_list[1]),
                           temp_list[2].replace("\'","/").replace(" ","0").replace('"','')])
    else:
        if last_type == 'tag':
            tag_list.append(chunk[1:])
        elif last_type == 'category':
            category_list.append(parse_cat(chunk.split('\n')))
        elif last_type == 'account':
            account_list.append(parse_acct(chunk.split('\n')))
        elif last_type == 'transaction':
            tran_list = parse_tran(counter,account,chunk.split('\n'))
            for x in tran_list:
                transaction_list.append(x)
        elif last_type == 'investment':
            investment_list.append(parse_inv(counter,account,chunk.split('\n')))
        elif last_type == 'memorized':
            memorized_list.append(chunk[1:])
        else:
            print("Something is missing.  This line is unaccounted for.")
    if chunk[:6] == '!Type:' and chunk.split('\n')[0] not in type_list:
        type_list_index.append([counter,chunk])
        type_list.append(chunk.split('\n')[0])
    counter += 1

#To account for multi-currency sets up in Quicken, please adjust below accordingly
print()
usd_accounts = ['USD Account1','USD Account2']
sgd_accounts = ['SGD Account1','SGD Account2']
exchange = 0.754432

usd_accounts = [[x,1/exchange] for x in usd_accounts]
sgd_accounts = [[x,1] for x in sgd_accounts]
account_rates = pd.DataFrame(usd_accounts + sgd_accounts,columns = ['Account','Rate'])

#Convert to DataFrames
tag_list = pd.DataFrame(tag_list,columns=['Tags'])
category_list = pd.DataFrame(category_list, columns = ['Category','Description','Tax-Related',
                                                       'Income/Expense','Budget Amount','Tax Schedule'])
account_list = pd.DataFrame(account_list,columns = ['Name','Type','Description','Credit Limit','Balance Date','Balance Amount']).drop_duplicates(subset='Name',keep='last').sort_values(by='Name').reset_index(drop=True)
security_list = pd.DataFrame(security_list,columns = ['Security','Type','Ticker'])
transaction_list = pd.DataFrame(transaction_list,columns=['Transaction ID','Account','Date','U-Amount','Amount','Cleared Status','Num','Payee','Memo','Address','Category','Split Type'])
transaction_list['Date'] = pd.to_datetime(transaction_list['Date'],format='%m/%d/%y')
transaction_list = transaction_list.merge(account_rates,on='Account',how='left')
transaction_list['Amount'] = transaction_list['Amount']*transaction_list['Rate']
investment_list = pd.DataFrame(investment_list,columns=['Transaction ID','Account','Date','Action','Security','Price','Quantity','Amount','Commission','Cleared Status','Text','Memo','Transfer Account','Transfer Amount'])
investment_list = investment_list.merge(account_rates,on='Account',how='left')
investment_list['Date'] = pd.to_datetime(investment_list['Date'],format='%m/%d/%y')
investment_list = investment_list.merge(security_list[['Security','Ticker','Type']],how='left',on='Security')
price_list = pd.DataFrame(price_list,columns = ['Ticker','Ticker Price','Date']).drop_duplicates()
price_list['Date'] = pd.to_datetime(price_list['Date'],format='%m/%d/%y')

#Reconfigure Investment File
end_date = pd.offsets.MonthEnd().rollforward(investment_list['Date'].max())
date_range = pd.date_range(start=investment_list['Date'].min(),end=end_date,freq='D')
new_base_file = pd.DataFrame({'Date':date_range})
new_base_file['Month'] = new_base_file['Date'].dt.strftime('%Y%m')
new_base_file['EOMonth'] = np.where(new_base_file['Date']==new_base_file['Date']+pd.tseries.offsets.MonthEnd(0),1,0)

investment_list_min = investment_list.groupby(['Account','Ticker'],as_index=False)['Date'].min()
investment_list_max = investment_list.groupby(['Account','Ticker'],as_index=False)['Date'].max()
investment_list_dates = investment_list_min.rename(columns={'Date':'Date_min'}).merge(
    investment_list_max.rename(columns={'Date':'Date_max'}),how='outer',on=['Account','Ticker']
    )
investment_list_dates = investment_list_dates[investment_list_dates['Ticker']!='']

#Create a new base file with all dates and Tickers to accurately show investments over time
investment_full = new_base_file.merge(investment_list,how='left',on='Date')
investment_list['Temp'] = investment_list['Ticker'] + '|' + investment_list['Account']
ticker_list = investment_list[investment_list['Ticker'].astype(str)!='nan']['Temp'].unique()
tickerdate = [(x,y) for x in date_range for y in ticker_list]
tickerdate = pd.DataFrame(tickerdate,columns = ['Date','Temp'])
new = tickerdate["Temp"].str.split("|", n = 1, expand = True) 
tickerdate['Ticker'] = new[0]
tickerdate['Account'] = new[1]
tickerdate['EOMonth'] = np.where(tickerdate['Date']==tickerdate['Date']+pd.tseries.offsets.MonthEnd(0),1,0)
del tickerdate['Temp']
del investment_list['Temp']
investment_full = pd.concat([investment_full,tickerdate]).drop_duplicates(subset=['Account','Ticker','Date','Transaction ID'])
investment_full = investment_full.merge(price_list,how='left',on=['Date','Ticker']).sort_values(by=['Account','Ticker','Date','Amount'],ascending=True)
investment_full['Amount'] = investment_full['Amount'].fillna(0)
investment_count = investment_full[['Account','Date','Ticker','Amount']].groupby(by=['Account','Date','Ticker'],as_index=False)['Amount'].count().rename(columns={'Amount':'CountCheck'})
investment_full = investment_full.merge(investment_count,how='left',on=['Account','Date','Ticker'])
investment_full = investment_full[~((investment_full['CountCheck'].fillna(1)>1)&(investment_full['Action'].fillna('')==''))]
del investment_full['CountCheck']

#Merge the base file onto the investment and remove dates before and after relevant transactions
investment_full = investment_full.merge(investment_list_dates,how='left',on=['Account','Ticker'])
investment_full = investment_full[investment_full['Date_min'].fillna('1939-01-01')<=investment_full['Date']]
investment_full = investment_full[investment_full['Date_max'].fillna('2099-01-01')+datetime.timedelta(days=32)>=investment_full['Date']]

#Stock Splits
investment_full['Splits'] = np.where(investment_full['Action']=='StkSplit',investment_full['Quantity'].fillna(0)/10,0)
investment_full['Quantity'] = np.where(investment_full['Action']=='StkSplit',0,investment_full['Quantity'])
#Cumulative Total Stock
investment_full['CumStock_prep'] = np.where(investment_full['Action']=='Sell',investment_full['Quantity']*-1,investment_full['Quantity'])
investment_full['CumStock_Pos'] = np.where(investment_full['Action']=='Sell',0,investment_full['Quantity'])
investment_full['CumStock_Pos'] = investment_full['CumStock_Pos'].fillna(0)
investment_full['CumStock_Pos'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_Pos'].cumsum()
investment_full['CumStock_Pos_shift'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_Pos'].shift(1)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'].fillna(0)
investment_full['CumStock'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_prep'].cumsum()
investment_full['Quantity'] = np.where(investment_full['Action']=='StkSplit',investment_full['CumStock'].fillna(0).astype(int)*(investment_full['Splits'].fillna(0).astype(int)-1),investment_full['Quantity'])

investment_full['CumStock_prep'] = np.where(investment_full['Action']=='Sell',investment_full['Quantity']*-1,investment_full['Quantity'])
investment_full['CumStock_Pos'] = np.where(investment_full['Action']=='Sell',0,investment_full['Quantity'])
investment_full['CumStock_Pos'] = investment_full['CumStock_Pos'].fillna(0)
investment_full['CumStock_Pos'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_Pos'].cumsum()
investment_full['CumStock_Pos_shift'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_Pos'].shift(1)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'].fillna(0)
investment_full['CumStock'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_prep'].cumsum()
#Cumulative Buy Only
investment_full['CumStock_prep'] = np.where(investment_full['Action']=='Buy',investment_full['Quantity'],0)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'].fillna(0)
investment_full['CumStock_prep_cum'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_prep'].cumsum()
investment_full['CumStockBuy_shift'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_prep_cum'].shift(1)
investment_full = investment_full.round(4)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'] + np.where(investment_full['Action']=='Sell',np.where(investment_full['Quantity'].round(4)>=investment_full['CumStockBuy_shift'].round(4),-1*investment_full['CumStockBuy_shift'],np.where(investment_full['Quantity'].round(4)<=(investment_full['CumStock_Pos_shift']-investment_full['CumStockBuy_shift']).round(4),0,-investment_full['Quantity'])),0)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'].fillna(0)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'] + np.where(investment_full['Action'].isin(['ShrsIn','ReinvInc']),investment_full['Quantity'],np.where(investment_full['Action']=='ShrsOut',-investment_full['Quantity'],0))
investment_full['CumStockBuy'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_prep'].cumsum()
investment_full['Quantity'] = np.where(investment_full['Action']=='StkSplit',investment_full['CumStockBuy']*(investment_full['Splits'].fillna(0).astype(int)-1),investment_full['Quantity'])

investment_full['CumStock_prep'] = np.where(investment_full['Action'].isin(['Buy','StkSplit']),investment_full['Quantity'],0)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'].fillna(0)
investment_full['CumStock_prep_cum'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_prep'].cumsum()
investment_full['CumStockBuy_shift'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_prep_cum'].shift(1)
investment_full = investment_full.round(4)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'] + np.where(investment_full['Action']=='Sell',np.where(investment_full['Quantity'].round(4)>=investment_full['CumStockBuy_shift'].round(4),-1*investment_full['CumStockBuy_shift'],np.where(investment_full['Quantity'].round(4)<=(investment_full['CumStock_Pos_shift']-investment_full['CumStockBuy_shift']).round(4),0,-investment_full['Quantity'])),0)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'].fillna(0)
investment_full['CumStock_prep'] = investment_full['CumStock_prep'] + np.where(investment_full['Action'].isin(['ShrsIn','ReinvInc']),investment_full['Quantity'],np.where(investment_full['Action']=='ShrsOut',-investment_full['Quantity'],0))
investment_full['CumStockBuy'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStock_prep'].cumsum()
investment_full['CumStockBuy_shift'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumStockBuy'].shift(1)
investment_full = investment_full.drop(['CumStock_prep','CumStock_Pos','CumStock_Pos_shift','CumStock_prep_cum'],axis=1)
#Cumulative Div Only
investment_full['CumStockDiv'] = investment_full['CumStock'] - investment_full['CumStockBuy']
investment_full['CumCost_prep'] = np.where(investment_full['Action'].isin(['Buy','ReinvInt']),investment_full['Amount'],0)
investment_full['CumCost_prep'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumCost_prep'].cumsum()
investment_full['CumCost_prep_shift'] = investment_full.groupby(['Account','Ticker'],as_index=False)['CumCost_prep'].shift(1)
investment_full['CumCost_sellprep'] = np.where(investment_full['Action'] == 'Sell',np.where(investment_full['CumStockBuy']!=investment_full['CumStockBuy_shift'],-investment_full['CumCost_prep_shift']*(((investment_full['CumStockBuy_shift']-investment_full['CumStockBuy'])/investment_full['CumStockBuy_shift'])),np.NaN),np.NaN)
investment_full['CumCost_sellprep'] = investment_full.groupby(['Account','Ticker'])['CumCost_sellprep'].fillna(method='ffill').fillna(0)
investment_full['CumCost'] = investment_full['CumCost_sellprep'] + investment_full['CumCost_prep']
investment_full['CumCost_shift'] = investment_full.groupby(['Account','Ticker'])['CumCost_prep'].shift(1)
investment_full['Ticker Price Alt'] = investment_full.groupby(['Account','Ticker'])['Ticker Price'].fillna(method='ffill')
investment_market = investment_full.drop_duplicates(subset=['Account','Ticker','Date'],keep='last')
investment_market['Market Value'] = (investment_market['CumStock'] * investment_market['Ticker Price Alt']).fillna(0)
investment_full = investment_full.merge(investment_market[['Account','Ticker','Date','Market Value']],how='left',on=['Account','Ticker','Date'])
investment_full['Profit'] = investment_full['Market Value'] - investment_full['CumCost']
investment_full['Total Gain'] = np.where(investment_full['Action']=='Sell',investment_full['Amount'] - investment_full.groupby(['Account','Ticker'])['CumCost'].shift(1) + investment_full['CumCost'],0)
investment_full['Dividend Gain'] = (investment_full['Total Gain'] * (investment_full.groupby(['Account','Ticker'])['CumStockDiv'].shift(1)-investment_full['CumStockDiv'])/(investment_full.groupby(['Account','Ticker'])['CumStock'].shift(1)-investment_full['CumStock'])).fillna(0)
investment_full['Dividend Gain'] = investment_full['Dividend Gain'] + np.where(investment_full['Action'].isin(['Div','MiscIncX']),investment_full['Amount'],np.where(investment_full['Action']=='BuyDiv',-investment_full['Amount'],0))
investment_full['Total Gain'] = investment_full['Total Gain'] + np.where(investment_full['Action'].isin(['Div','MiscIncX']),investment_full['Amount'],np.where(investment_full['Action']=='BuyDiv',-investment_full['Amount'],0))
investment_full['Value Gain'] = (investment_full['Total Gain'] * (investment_full.groupby(['Account','Ticker'])['CumStockBuy'].shift(1)-investment_full['CumStockBuy'])/(investment_full.groupby(['Account','Ticker'])['CumStock'].shift(1)-investment_full['CumStock'])).fillna(0)
investment_full = investment_full[(investment_full['EOMonth']==1)|(investment_full['Memo'].astype(str)!='nan')]
investment_full = investment_full.drop([x for x in investment_full.columns if 'prep' in x or 'shift' in x],axis=1)
investment_full = investment_full[investment_full['Account'].fillna('')!='']
investment_full['Transfers'] = np.where(investment_full['Action'].isin(['XIn','Cash','ContribX']),investment_full['Amount'],np.where(investment_full['Action'].isin(['XOut','WithdrwX']),-investment_full['Amount'],0))
investment_full['Transfers'] = np.where(investment_full['Transfer Account'].fillna('')=='',investment_full['Transfers'],np.where(investment_full['Action'].isin(['XIn','Cash','ContribX','BuyDiv']),investment_full['Amount'],np.where(investment_full['Action'].isin(['Sell','XOut','WithdrwX']),-investment_full['Amount'],0)))
investment_full['Interest'] = np.where(investment_full['Action']=='IntInc',investment_full['Amount'],np.where(investment_full['Action']=='ReinvInt',-investment_full['Amount'],0))
investment_full['Cash'] = investment_full['Interest'].fillna(0) + investment_full['Transfers'].fillna(0) + investment_full['Total Gain'].fillna(0) - investment_full['CumCost'].fillna(0) + investment_full.groupby(['Account','Ticker'])['CumCost'].shift(1).fillna(0)
investment_full = investment_full.sort_values(by=['Account','Date','Cash'],ascending=[True,True,False])
investment_full['Cash'] = investment_full.groupby(['Account'],as_index=False)['Cash'].cumsum()

#Export all DataFrames to CSVs
tag_list.to_csv("tag list.csv",index=False)
category_list.to_csv("category list.csv",index=False)
account_list.to_csv("account list.csv",index=False)
security_list.to_csv("security list.csv",index=False)
transaction_list.to_csv("Spending File.csv",index=False)
investment_list.to_csv("investment list.csv",index=False)
price_list.to_csv("price list.csv",index=False)
investment_full['Month'] = investment_full['Date'].dt.strftime('%Y-%m-01')
investment_full.to_csv("Investment File.csv",index=False)