#@auto-fold regex /./

from datetime import datetime, timedelta,date
import requests as r, pandas as pd,time,sys
sys.path.insert(0,'C:/Finance/projects/')
import env,googleapi as gapi
import selenium.webdriver
from selenium.webdriver.chrome.options import Options
from pandas.io.json import json_normalize
global cookies_dict
global gf
cookies_dict ={}
gf = pd.DataFrame()
gf2 = pd.DataFrame()
baseRestUrl = "https://live.trading212.com/rest"
options = Options()
options.add_argument('user-data-dir=insert data file path')
driver = selenium.webdriver.Chrome(executable_path= 'driver file path',  options  = options)
driver.get('https://live.trading212.com/')
time.sleep(30)

def get_dates() -> list:
    StartDate = datetime.strptime('2020-01-01','%Y-%m-%d').date()
    EndDate = datetime.today().date() #datetime.strptime('2020-12-31','%Y-%m-%d').date()  #
    return([StartDate,EndDate])

def get_cookies() -> dict:
    """ Get the current user cookie"""
    cookies = driver.get_cookies()
    for cookie in cookies:
        cookies_dict[cookie['name']] = cookie['value']
    cookies_dict.update(cookies_dict)
    return cookies_dict

def get_headers() -> dict:
    return  {
        'X-Trader-Client': 'application=WC4, version=5.119.0, accountId=1653026, dUUID=0cf8c906-f2ae-4120-90e4-4df136c264a2',
        'sec-ch-ua-mobile': '?0',
        'Content-Type': 'application/json',
        'Origin': 'https://live.trading212.com',
        'Referer': 'https://live.trading212.com/',}

def form_data(StartDate,EndDate) -> dict:
    return """{
       "timeFrom":"%sT00:00:00+00:00",
       "timeTo":"%sT23:59:59+00:00",
       "reportFormat":"CSV",
       "dataIncluded":{
          "includeOrders":true,
          "includeDividends":true,
          "includeTransactions":true
           }
    }""" % (StartDate,EndDate)

def get_acc_info():
    """Get current account info"""
    global gf2
    resps = r.get(baseRestUrl+'/v2/account', headers=get_headers(),cookies=cookies_dict)
    gf2 = gf2.append(json_normalize(resps.json()))
    return  resps.json()['id']

def switch_account():
    """This will switch between ISA and NON-ISA accounts"""
    acc_id =[]
    accs = r.get(baseRestUrl+'/customer/accounts/funds',headers=get_headers(),cookies=cookies_dict)
    for k, v in accs.json().items():
        if v['tradingType'] in ('EQUITY', 'ISA'):
            acc_id.append(v['accountId'])
    for id in acc_id:
        if get_acc_info() == id: ## NOTE: if the current account id is the same then switch account
            pass
        else:
            payload = {'accountId': id}
            api_url = r.post(baseRestUrl+'/v2/account/switch',
            headers=get_headers(), json=payload, cookies=cookies_dict)
            print('Switching to account ID: {}'.format(id))
            cookies_dict.update(api_url.cookies)
            acc_id.clear()

def clear_notfi():
    """Clear all notifications created"""
    resp = r.get(baseRestUrl+'/v2/notifications',headers=get_headers(), cookies=cookies_dict)
    ids = ','.join(map(str, [i['id'] for i in resp.json()[:8]]))
    resp = r.delete(baseRestUrl+'/v1/notifications/'+ids,headers=get_headers(), cookies=cookies_dict)
    return 'Delete the previus 8 notifications: status_code: ' + str(resp.status_code)

def export_transactions():
    """Export the data; This will create a report ID and clear notifications"""
    delta = timedelta(days = 365)
    StartDate = get_dates()[0]
    EndDate = get_dates()[1]
    while StartDate < EndDate:
        resp = r.post(baseRestUrl+'/v1/report-exports', headers=get_headers(), cookies=cookies_dict,
                data=form_data(StartDate, StartDate + timedelta(hours = 8759, seconds= 59)))
        report_id = resp.json()['reportId']
        print('Exporting transactions from {} to {}, report id: {}, account ID {}'.format(StartDate
                                    , StartDate + timedelta(hours = 8759, seconds= 59), report_id, get_acc_info()))
        time.sleep(30)
        download_report(report_id)
        StartDate += delta
    clear_notfi()

def download_report(report_id):
    """Download the report with transaction data"""
    resp = r.get(baseRestUrl+'/v1/report-exports', headers=get_headers(), cookies=cookies_dict)
    for item in resp.json():
        if report_id == item['reportId']:
            if item['status'] != 'Finished':
                time.sleep(30)
            else:
                try:
                    df = pd.read_csv(item['downloadLink'])
                    df['Account ID'] = get_acc_info()
                    gf = gf.append(df)
                except:
                    print('No columns to parse from file')

def save_to_gsheets():
    """"Move the transaction data into google sheet"""
    gf['Action'] = gf['Action'].replace(regex=[r'Market ','Limit ','Stop '], value='')
    gf['Action'] = gf['Action'].replace('Dividend (Ordinary)','Div')
    gf['Action'] = gf['Action'].str.strip().str.capitalize()
    gf['Transaction Date'] = gf.Time.str[:10]
    gf['Stock Split Ratio'] = 0
    gf = gf.loc[gf['Action'].isin(['Buy','Sell'])]
    gf.drop_duplicates(inplace=True,  keep='first')
    sh = env.open_wb('18HjRhb8maIt0ypGxSAmjz592_1oQZqEN0f915RlGsjw').worksheet('Manual Data')
    mf = pd.DataFrame(sh.get_all_values())
    mf.columns = mf.iloc[0]
    mf = mf[1:]

    df = pd.concat([gf, mf], sort=False)
    df = df.reset_index(drop=True)
    df['Time'] = pd.to_datetime(df['Time'])
    df = df[["Account ID","Action","Charge amount (GBP)","Currency (Price / share)","Currency (Withholding tax)","Exchange rate",
        "Finra fee (GBP)","ID","ISIN","Name","No. of shares","Notes","Price / share","Result (GBP)","Ticker","Time","Total (GBP)",
        "Transaction fee (GBP)","Withholding tax","Transaction Date","Stock Split Ratio"]]
    df = df.sort_values(['Time'], ascending=True )

    env.rep_data_sh(df,'18HjRhb8maIt0ypGxSAmjz592_1oQZqEN0f915RlGsjw','T212 Data',df.shape[1])

get_cookies()
get_acc_info()
export_transactions()
switch_account()
export_transactions()
save_to_gsheets()
