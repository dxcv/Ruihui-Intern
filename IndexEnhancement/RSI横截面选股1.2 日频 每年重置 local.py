# -*- coding: utf-8 -*-
"""
@author: Michael Wang

`Based on Version 1.1`

- 港股
- 市值大于100亿
- 5e7
- 每年重置资本金
- RSI线 分为快慢
- price 分为交易/停牌，需要区分对待；对于停牌的，需要用nan，并在计算中不予以考虑

updated on 2018/11/23
"""
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import talib
#from data_reader import get_muti_close_day, get_index_day, get_hk_index_day
#import pymssql
# pylint: disable=E1101,E1103
# pylint: disable=W0212,W0231,W0703,W0622
CAPITAL = 5e7
TODAY = datetime.date.today().strftime('%Y-%m-%d')

# 获取数据
underLying = 'hs300'#zz500
hs300 = pd.read_hdf(r"PriceData_1120_FullPool.h5",'hs300')
price = pd.read_hdf(r"PriceData_1120_FullPool.h5",'price')
component = pd.read_hdf(r"PriceData_1120_FullPool.h5",'component')
priceFill = price.fillna(method='ffill')

#%%
#思路：把不在当前成份股列表的股票标记为nan
compo = component.pivot_table(values='weight', index = 'Date', columns='code')
compo = compo.fillna(0)
compo = compo.reindex(price.index, method = 'ffill') #不能ffill

price[compo==0] = np.nan
priceFill[compo==0] = np.nan

#%% 
def 仓位计算和优化(arg=30, fast = False):
    global RSI_arg

    RSI_arg = arg
    RSI = priceFill.apply(talib.RSI, args=(RSI_arg,))

    RSI[price.isna()] = 50
#    if fast: RSI =100-RSI
    分母=abs(RSI.T-50).sum()
    RSI_normalized = ((RSI.T-50)/分母).T
    RSI_normalized.fillna(0,inplace=True)
    pos = RSI_normalized[RSI_normalized>0]

    # pos[pos.T.sum()>0.1] *= 1.5
    # pos[pos.T.sum()>0.2] *= 1.2
    # pos[pos.T.sum()>0.3] *= 1.2
    pos[pos.T.sum()<0.4] *= 0.8
    pos[pos.T.sum()<0.3] *= 0.5
#    if not fast:
    pos[pos.T.sum()>0.6] *= 1.1
    pos[pos.T.sum()>0.7] *= 1.1
    pos[pos.T.sum()>0.8] *= 1.1
    # 将总和超出1的仓位，除以总和，归为1
    pos[pos.T.sum()>1] = pos[pos.T.sum()>1].divide(pos.T.sum()[pos.T.sum()>1],axis=0)
    pos.fillna(0, inplace = True)

    return pos, RSI


posSlow, RSI_Slow = 仓位计算和优化(40)
posFast, RSI_Fast = 仓位计算和优化(10, fast=True)
posSlow[(posSlow.T.sum()<0.50) & (posSlow.T.sum()>0.05)] = posFast
posSlow[(posSlow.T.sum()>0.9) & (posFast.T.sum()<0.32)] = posFast

def check(y):#看一下具体每一年的表现
    year = str(y)
    posSlow[year].T.sum().plot(c='r')
    plt.twinx()
    hs300[year].plot()
    plt.show()
    
    posFast[year].T.sum().plot(c='r')
    plt.twinx()
    hs300[year].plot()
    plt.show()
    
    NAV0[year].plot(c='r')
    (hs300[year]/hs300[year].iloc[0]).plot()
    plt.show()
#%%
# share记录了实时的仓位信息
# 注意：交易时间为交易日的收盘前
share = posSlow#[pos.index.dayofweek == 交易日]
share = share.reindex(posSlow.index)
share.fillna(method='ffill',inplace=True)
price_change = priceFill.diff()

#近似 & 按月复利 按年重置
daily_pnl=pd.DataFrame()
share_last_month = pd.DataFrame(columns=share.columns, index=share.index[0:1])
share_last_month.fillna(0, inplace=True)
for year in range(2008,2019):
    initialCaptial = CAPITAL
    for month in range(1,13):
        this_month = str(year)+'-'+str(month)
        print('\r' + this_month, end='')
        try:
            temp = round(share[this_month] * initialCaptial/ price,-2)
        except:
            continue
        share[this_month] = temp.fillna(method='ffill')
        share_last_day = share[this_month].shift(1)
        share_last_day.iloc[0] = share_last_month.iloc[-1] * price_change.iloc[-1]
        share_last_month = share[this_month]
        # 当日收益 = 昨日share * 今日涨跌幅 ; 每月第一行缺失

        daily_pnl = daily_pnl.append(price_change[this_month] * share_last_day)
        initialCaptial += daily_pnl[this_month].T.sum().sum()

print("回测完毕")
# 手续费，卖出时一次性收取
fee_rate = 0.00
fee = (share.diff()[share<share.shift(1)] * priceFill * fee_rate).fillna(0).abs()
daily_pnl -= fee
# 按年清空
cum_pnl = pd.DataFrame(daily_pnl.T.sum(),columns=['pnl'])
cum_pnl['year']=cum_pnl.index.year
cum_pnl = cum_pnl.groupby('year')['pnl'].cumsum()
NAV = (daily_pnl.T.sum()/CAPITAL).cumsum()+1
NAV0 = (cum_pnl / CAPITAL)+1
#换手率
换手率=((share * price).divide((share * price).T.sum(),axis=0).diff().abs().T.sum() / 2)
print("每日换手率 {:.2%}".format(换手率.mean()))
print("年化换手率 {:.2%}".format(换手率.mean()*250))
print(换手率.resample('y').sum())

def 图像绘制():
    global hs300
    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.figure(figsize=(9,6))
    
    NAV.plot(label='按月复利 每年重置 累计值')
    NAV0.plot(label='按月复利 每年重置')
    exec(underLying+' = '+underLying+".reindex(daily_pnl.index)")
    exec(underLying+' = '+underLying+'/'+underLying+'.iloc[0]')
    exec(underLying+".plot(label='"+underLying+"')")
    plt.legend(fontsize=11)
    # plt.title('RSI参数={}，日频，无手续费'.format(RSI_arg),fontsize=15)
    plt.title('RSI参数={}，日频，手续费{:.1f}‰'.format(RSI_arg, fee_rate*1000), fontsize=15)
    # plt.title('RSI参数={}，交易日={}，手续费{:.1f}‰'.format(RSI_arg, 交易日+1, fee_rate*1000), fontsize=15)
    plt.grid(axis='both')
    plt.show()
图像绘制()
#%% 
def excel输出():
    df = pd.DataFrame({'Daily_pnl':daily_pnl.T.sum(),
                       '累计PNL':cum_pnl,
                       '账户价值':cum_pnl+CAPITAL,
                       'NAV':NAV0, 'NAV累计':NAV},
                       index = daily_pnl.index)
    df.index.name = 'date'
    df.to_excel('RSI横截面_{}纯多头_收益率明细_{}_日.xlsx'.format(underLying, TODAY),
                sheet_name = 'RSI={},日频'.format(RSI_arg))
    
    df = daily_pnl.join(share, lsuffix='_pnl',rsuffix='_share')
    df = df.join(price,rsuffix='_price')
    df = df.join(RSI_Fast, rsuffix='_RSI_Fast')
    df = df.join(RSI_Slow, rsuffix='_RSI_Slow')
    df.sort_index(axis=1,inplace=True)
    df.columns = pd.MultiIndex.from_product([daily_pnl.columns,['price','RSI_Fast','RSI_Slow','daily_pnl','share']])
    df.to_excel('RSI横截面_{}纯多头_持仓明细_{}_日.xlsx'.format(underLying, TODAY),
                sheet_name = 'RSI={},日频'.format(RSI_arg))
excel输出()

#%% 获取实时数据
from WindPy import *
w.start()
data_today = pd.DataFrame()
for i in pool:
    print(i, end = '\r')
    rawdata = w.wsi(i, "close", "%s 14:55:00" % TODAY, "%s 14:56:00" % TODAY, "")
    rawdata = pd.DataFrame({i:rawdata.Data[0]},index=rawdata.Times)
    data_today = pd.concat([data_today, rawdata], axis=1)
data_close = data_today[data_today.index.minute==55]
data_close = data_close.astype(float)

price = pd.concat([price, data_close], sort=False)
priceFill = price.fillna(method='ffill')
print("New Data Loaded!", TODAY)

# 计算新仓位
posSlow, RSI_Slow = 仓位计算和优化(40)
posFast, RSI_Fast = 仓位计算和优化(10, fast=True)
posSlow[(posSlow.T.sum()<0.50) & (posSlow.T.sum()>0.05)] = posFast
posSlow[(posSlow.T.sum()>0.95) & (posFast.T.sum()<0.32)] = posFast

# 计算新持股数
share = round(posSlow * initialCaptial/ price, -2)

#写文件
signal = share.diff().iloc[-1]
signal.dropna(inplace=True)
signal = signal[signal!=0]
csv = pd.DataFrame(columns=['local_entrust_no','fund_account','exchange_type','stock_code','entrust_bs','entrust_prop','entrust_price','entrust_amount','batch_no'])
for i in range(len(signal)):
    symbol = signal.index[i]
    amount = int(signal[symbol])
    exchange_type = (symbol[-2:]=='SZ') +1
    entrust_bs = int(amount<0)+1
    entrust_prop = 'R' if exchange_type==1 else 'U'
    csv.loc[i] = [i+1, 7047709, exchange_type, symbol[:-3], 
                  entrust_bs, entrust_prop, data_close[symbol][0],
                  abs(amount), '']
import datetime
csv.to_csv(r'\\192.168.0.29\Stock\orders\RSI\order_{}.{}00000.csv'.format('RSItest', datetime.datetime.now().strftime('%Y%m%d%H%M'))
            ,index=False)