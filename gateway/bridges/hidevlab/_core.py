"""HiDevLab HTTP client. No browser, browser cookies, or AI runtime required.

Password and SMS code are read without echo. Default operation only plans changes.
The private web protocol was inspected on 2026-10-27 and can change.
"""
import argparse
import csv
import getpass
import html
import json
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import requests
import session_cache

ROOT = 'https://hidevlab.huawei.com'
API = ROOT + '/hidevlabgatewayservice/com.huawei.ipd.hicomputing.lab:hidevlabservice/hidevlabservice'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36'


class ProtocolError(Exception):
    pass


class APIError(ProtocolError):
    def __init__(self,path,code):
        self.code=code
        super().__init__('API '+path+' returned business code '+str(code))


class AuthExpired(ProtocolError):
    pass


def truth(value):
    return str(value).lower() in ('true', '1')


def mask(phone):
    return phone[:3] + '****' + phone[-4:]


def matched(rows, name, phone):
    same = [r for r in rows if r.get('phoneNumber') in (phone, mask(phone))]
    exact = [r for r in same if r.get('memberName', '').strip() == name.strip()]
    if len(exact) == 1 and len(same) == 1:
        return exact[0]
    if same or any(r.get('memberName', '').strip() == name.strip() for r in rows):
        raise ProtocolError('Name or masked-phone collision; manual review required for ' + name)
    return None


class Client:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({'User-Agent': UA})
        self.csrf = None
        self.local = {}
        self.page = {}
        self.cache_created = None

    def verify_identity(self,account):
        me=self.api('GET','/hwaccount/getUserInfo')
        if not any(me.get(key) in (account,mask(account),'0086'+account) for key in ('loginID','phone')):
            raise ProtocolError('Logged-in account does not match requested account')
        return me

    def save_cache(self,account,path):
        session_cache.save(path,account,self.s,self.csrf,self.cache_created)

    def resume_cache(self,account,path,max_age_hours=168):
        if not path.exists():
            return False
        try:
            self.csrf,self.cache_created=session_cache.load(path,account,self.s,max_age_hours)
        except (session_cache.CacheError,OSError,TypeError,KeyError):
            print('Encrypted cache unavailable or expired; fresh login required.',flush=True)
            self.__init__()
            return False
        try:
            self.verify_identity(account)
        except APIError as exc:
            if exc.code not in (401,412):
                raise
            self.__init__()
            print('Server session expired; fresh login required.',flush=True)
            return False
        except AuthExpired:
            self.__init__()
            print('Server session expired; fresh login required.',flush=True)
            return False
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 401:
                raise
            self.__init__()
            print('Server session expired; fresh login required.',flush=True)
            return False
        # Network failures stop the run; they do not trigger another SMS login.
        print('Encrypted HTTP session restored and account verified; no password/SMS needed.',flush=True)
        self.save_cache(account,path)
        return True

    def request(self, method, url, **kwargs):
        # Do not retry POST: a timeout can mean the server already committed it.
        response = self.s.request(method, url, timeout=30, **kwargs)
        response.raise_for_status()
        if response.headers.get('x-csrf-token'):
            self.csrf = response.headers['x-csrf-token']
        return response

    def cas(self, endpoint, data):
        local = self.local
        body = {k: local[k] for k in ('reqClientType','loginChannel','clientID','lang','state') if k in local}
        body.update(languageCode=local.get('lang', 'zh-cn'))
        body.update({k: self.page[k] for k in ('pageToken','pageTokenKey','localStorageID') if k in self.page})
        body.update(data)
        base = local.get('localHttpsAjaxPath') or self.cas_origin + '/CAS/IDM_W'
        response = self.request('POST', base.rstrip('/') + '/ajaxHandler/' + endpoint,
            params={'cVersion':local.get('cookieVersion','UP_CAS_6.26.3.100'), 'reflushCode':'0.'+str(secrets.randbelow(10**16))},
            data=body, headers={'Referer':self.cas_url,'Origin':self.cas_origin})
        result = response.json()
        for key in ('pageToken','pageTokenKey','localStorageID'):
            if key in result:
                self.page[key] = result[key]
        return result

    def oauth_step(self, response):
        p = urlsplit(response.url)
        if p.hostname not in ('oauth-login.cloud.huawei.com','oauth-login1.cloud.huawei.com'):
            raise ProtocolError('Unexpected OAuth origin')
        endpoint = 'login' if p.path.endswith('/loginCallback') else 'getLoginWay'
        return self.request('POST', 'https://' + p.netloc + '/oauth2/ajax/'+endpoint, data=p.query,
            headers={'interfaceVersion':'v3','fromLoginAuth':'false','Content-Type':'application/x-www-form-urlencoded','Referer':response.url}).json()

    def login(self, account, password, allow_sms=False):
        target = ROOT + '/personal-center/projectSpace'
        response = self.request('GET', API+'/hwaccount/login', params={'loginType':'login','redirect':target})
        oauth = self.oauth_step(response)
        cas_url = oauth.get('loginInteractInfo',{}).get('cas',{}).get('casLoginRedirectUrl')
        if not cas_url:
            raise ProtocolError('Huawei CAS login URL missing')
        if urlsplit(cas_url).hostname not in ('id1.cloud.huawei.com','id.cloud.huawei.com'):
            raise ProtocolError('Unexpected CAS origin')
        response = self.request('GET', cas_url)
        self.cas_url = response.url
        p = urlsplit(response.url)
        self.cas_origin = 'https://' + p.netloc
        params = dict(parse_qsl(p.query))
        params.update(interfaceName='login/getPageInfo',urlParam=p.query,pageName=p.path.rsplit('/',1)[-1].replace('.html',''))
        self.page = self.cas('login/getPageInfo',params)
        if not truth(self.page.get('isSuccess')):
            raise ProtocolError('CAS page initialization failed: ' + str(self.page.get('errorCode')))
        self.local = {k:html.unescape(v) if isinstance(v,str) else v for k,v in self.page.get('localInfo',{}).items()}
        data = {k:self.local[k] for k in ('loginUrl','service','quickAuth','scope') if k in self.local}
        data.update(userAccount=account,isThirdBind=0)
        risk = self.cas('chkRisk',dict(data,operType=0))
        if not truth(risk.get('isSuccess')):
            raise ProtocolError('Account check failed: ' + str(risk.get('errorCode')))
        if truth(risk.get('isNeedImageCode')):
            raise ProtocolError('Huawei requires CAPTCHA. No password sent; no challenge bypass attempted.')
        data.update(password=password, lowLogin=risk.get('lowLogin',False))
        result = self.cas('remoteLogin',data)
        if str(result.get('errorCode')) in ('10002080','10012072','10012076'):
            detail = json.loads(result.get('errorDesc','{}'))
            if not allow_sms:
                raise ProtocolError('Huawei requires new-session verification. Run with --sms for terminal SMS verification.')
            channels = [x for x in detail.get('authCodeSentList',[]) if str(x.get('accountType')) in ('2','6')]
            if len(channels) != 1:
                raise ProtocolError('Cannot unambiguously select an SMS verification channel')
            channel = channels[0]
            if not truth(channel.get('sent')):
                sent = self.cas('getSMSCodeV3',{'userAccount':account,'accountType':2,
                    'mobilePhone':channel['name'],'operType':'8','smsReqType':6,'siteID':risk.get('siteID')})
                if not truth(sent.get('isSuccess')):
                    raise ProtocolError('SMS request failed: ' + str(sent.get('errorCode')))
                print('SMS sent to the Huawei account verification phone.',flush=True)
            code = getpass.getpass('SMS verification code (hidden; r to resend): ')
            while code.lower() == 'r':
                sent = self.cas('getSMSCodeV3',{'userAccount':account,'accountType':2,
                    'mobilePhone':channel['name'],'operType':'8','smsReqType':6,'siteID':risk.get('siteID')})
                if not truth(sent.get('isSuccess')):
                    raise ProtocolError('SMS resend rejected: '+str(sent.get('errorCode')))
                print('SMS resent in the same HTTP session.',flush=True)
                code=getpass.getpass('Latest SMS code (hidden; r to resend): ')
            if not re.fullmatch(r'\d{6}',code):
                raise ProtocolError('Expected a six-digit verification code; not submitted')
            data.update(twoStepVerifyCode=code,verifyAccountType=channel['accountType'],verifyUserAccount=channel['name'],opType=1)
            if detail.get('tipsSceneID') is not None:
                data['tipsSceneID'] = detail['tipsSceneID']
            result = self.cas('remoteLogin',data)
        if not truth(result.get('isSuccess')):
            raise ProtocolError('Huawei login did not complete: ' + str(result.get('errorCode')))
        callback = result.get('callbackURL')
        if not callback or urlsplit(callback).hostname not in ('id1.cloud.huawei.com','id.cloud.huawei.com','oauth-login1.cloud.huawei.com','oauth-login.cloud.huawei.com'):
            raise ProtocolError('No recognized login callback; additional login step required')
        response = self.request('GET',callback,headers={'Referer':self.cas_url})
        for _ in range(4):
            if urlsplit(response.url).hostname == 'hidevlab.huawei.com':
                break
            auth = self.oauth_step(response)
            callback = auth.get('code')
            if not isinstance(callback,str) or urlsplit(callback).hostname != 'hidevlab.huawei.com':
                raise ProtocolError('OAuth callback requires an additional authorization step')
            response = self.request('GET',callback,headers={'Referer':response.url})
        self.verify_identity(account)
        print('HTTP login and identity verification succeeded.',flush=True)

    def api(self, method, path, expected_code=200, **kwargs):
        headers = {'Referer':ROOT+'/personal-center/projectSpace','Origin':ROOT}
        if self.csrf:
            headers['x-csrf-token'] = self.csrf
        response = self.request(method,API+path,headers=headers,allow_redirects=False,**kwargs)
        if response.is_redirect:
            raise AuthExpired('Session expired or redirect returned; operation stopped')
        try:
            result = response.json()
        except ValueError:
            raise ProtocolError('Expected API JSON; operation stopped') from None
        if result.get('code') != expected_code:
            raise APIError(path,result.get('code'))
        return result.get('data')

    def members(self, project):
        rows=[]
        page=1
        while True:
            data=self.api('GET','/project/listTeamMember',params={'projectCode':project,'pageNum':page,'pageSize':45})
            batch=data.get('list',[])
            rows.extend(batch)
            if page >= int(data.get('pages',1)):
                return rows
            if not batch or page > 10000:
                raise ProtocolError('Inconsistent pagination; operation stopped')
            page+=1

    def role(self, project):
        metadata=self.api('GET','/project/getTitle/'+project)
        if metadata.get('projectCode') != project or not metadata.get('businessDomain'):
            raise ProtocolError('Project identity or business domain is missing')
        roles=self.api('GET','/hwaccount/listRole',params={'projectCode':project,'businessDomain':metadata['businessDomain']})
        selected=[r for r in roles if r.get('roleName')=='项目参与人']
        if len(selected)!=1:
            raise ProtocolError('Cannot determine ordinary participant role')
        return selected[0]['roleCode']

    def add(self, project, member, role):
        payload={'projectCode':project,'teamMemberList':[dict(member,roleCode=role)]}
        self.api('POST','/project/addTeamMember',json=payload)


def read_members(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not {'name','phone'}.issubset(reader.fieldnames or []):
            raise ProtocolError('CSV must contain name,phone columns')
        members=[]
        seen={}
        for row in reader:
            name,phone=row['name'].strip(),row['phone'].strip()
            if not name or not re.fullmatch(r'1\d{10}',phone):
                raise ProtocolError('Invalid name or phone in input CSV')
            if phone in seen and seen[phone]!=name:
                raise ProtocolError('Conflicting names for one phone')
            if phone not in seen:
                members.append({'name':name,'phone':phone})
                seen[phone]=name
        return members


