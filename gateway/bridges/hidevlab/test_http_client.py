import tempfile
import unittest
from pathlib import Path
from hidevlab_http import Client, ProtocolError, matched, read_members


class SafetyTests(unittest.TestCase):
    def test_mask_collision_is_not_treated_as_already_added(self):
        rows=[{'memberName':'Example A','phoneNumber':'138****1234'}]
        with self.assertRaises(ProtocolError):
            matched(rows,'Example B','13800001234')

    def test_duplicate_visible_identities_are_ambiguous(self):
        row={'memberName':'Example','phoneNumber':'138****1234'}
        with self.assertRaises(ProtocolError):
            matched([row,row],'Example','13800001234')

    def test_one_name_different_phone_needs_review(self):
        with self.assertRaises(ProtocolError):
            matched([{'memberName':'Example','phoneNumber':'139****9999'}],'Example','13800001234')

    def test_csv_deduplicates_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'members.csv'
            path.write_text('name,phone\nExample,13800001234\nExample,13800001234\n',encoding='utf-8')
            self.assertEqual(len(read_members(path)),1)
            path.write_text('name,phone\nExample A,13800001234\nExample B,13800001234\n',encoding='utf-8')
            with self.assertRaises(ProtocolError):
                read_members(path)

    def test_member_pagination_collects_every_page(self):
        client=Client()
        calls=[]
        def api(method,path,**kwargs):
            page=kwargs['params']['pageNum']
            calls.append(page)
            return {'pages':2,'list':[{'memberName':str(page)}]}
        client.api=api
        self.assertEqual(len(client.members('EXAMPLE')),2)
        self.assertEqual(calls,[1,2])

    def test_role_uses_project_business_domain(self):
        client=Client()
        def api(method,path,**kwargs):
            if path.startswith('/project/getTitle/'):
                return {'projectCode':'EXAMPLE','businessDomain':'public'}
            self.assertEqual(kwargs['params']['businessDomain'],'public')
            return [{'roleName':'项目参与人','roleCode':'student'}]
        client.api=api
        self.assertEqual(client.role('EXAMPLE'),'student')

    def test_add_uses_confirmed_payload_shape(self):
        client=Client()
        captured=[]
        client.api=lambda *args,**kwargs: captured.append((args,kwargs))
        client.add('EXAMPLE',{'name':'Example','phone':'13800001234'},'student')
        self.assertEqual(captured,[ (('POST','/project/addTeamMember'), {'json':{
            'projectCode':'EXAMPLE','teamMemberList':[{'name':'Example','phone':'13800001234','roleCode':'student'}]
        }}) ])

    def test_callback_uses_oauth_login_not_initialization(self):
        client=Client()
        class Response:
            url='https://oauth-login1.cloud.huawei.com/oauth2/v3/loginCallback?ticket=EXAMPLE'
            def json(self): return {'isSuccess':'true'}
        calls=[]
        def request(method,url,**kwargs):
            calls.append(url)
            return Response()
        client.request=request
        client.oauth_step(Response())
        self.assertEqual(calls,['https://oauth-login1.cloud.huawei.com/oauth2/ajax/login'])


if __name__=='__main__':
    unittest.main()
