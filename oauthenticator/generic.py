"""
Custom Authenticator to use generic OAuth2 with JupyterHub
"""


import json
import os
import base64
import urllib
import jwt

from tornado.auth import OAuth2Mixin
from tornado import gen, web

from tornado.httputil import url_concat
from tornado.httpclient import HTTPRequest, AsyncHTTPClient

from jupyterhub.auth import LocalAuthenticator

from traitlets import Unicode, Dict

from .oauth2 import OAuthLoginHandler, OAuthenticator


class GenericEnvMixin(OAuth2Mixin):
    _OAUTH_ACCESS_TOKEN_URL = os.environ.get('OAUTH2_TOKEN_URL', '')
    _OAUTH_AUTHORIZE_URL = os.environ.get('OAUTH2_AUTHORIZE_URL', '')


class GenericLoginHandler(OAuthLoginHandler, GenericEnvMixin):
    pass


class GenericOAuthenticator(OAuthenticator):

    login_service = Unicode(
        "GenericOAuth2",
        config=True
    )

    login_handler = GenericLoginHandler

    userdata_url = Unicode(
        os.environ.get('OAUTH2_USERDATA_URL', ''),
        config=True,
        help="Userdata url to get user data login information"
    )
    username_key = Unicode(
        os.environ.get('OAUTH2_USERNAME_KEY', 'username'),
        config=True,
        help="Userdata username key from returned json for USERDATA_URL"
    )
    userdata_params = Dict(
        os.environ.get('OAUTH2_USERDATA_PARAMS', {}),
        help="Userdata params to get user data login information"
    ).tag(config=True)

    userdata_method = Unicode(
        os.environ.get('OAUTH2_USERDATA_METHOD', 'GET'),
        config=True,
        help="Userdata method to get user data login information"
    )

    token_url = Unicode(
        os.environ.get('OAUTH2_TOKEN_URL', 'GET'),
        config=True,
        help="Userdata method to get user data login information"
    )

    @gen.coroutine
    def authenticate(self, handler, data=None):
        code = handler.get_argument("code")
        # TODO: Configure the curl_httpclient for tornado
        http_client = AsyncHTTPClient()

        params = dict(
            redirect_uri=self.get_callback_url(handler),
            code=code,
            grant_type='authorization_code',
            client_id=self.client_id,
            client_secret=self.client_secret,
            resource='7387c494-8bf5-4030-9e29-ed9f8d87f71c'
        )

        url = self.token_url

        b64key = base64.b64encode(
            bytes(
                "{}:{}".format(self.client_id, self.client_secret),
                "utf8"
            )
        )

        headers = {
            "Accept": "application/json",
            "User-Agent": "JupyterHub",
            "Authorization": "Basic {}".format(b64key.decode("utf8"))
        }
        req = HTTPRequest(url,
                          method="POST",
                          headers=headers,
                          body=urllib.parse.urlencode(params)  # Body is required for a POST...
                          )

        resp = yield http_client.fetch(req, raise_error=False)
        resp_json = json.loads(resp.body.decode('utf8', 'replace'))

        access_token = resp_json['id_token']
        token_type = resp_json['token_type']

        # Determine who the logged in user is
        headers = {
            "Accept": "application/json",
            "User-Agent": "JupyterHub",
            "Authorization": "{} {}".format(token_type, access_token)
        }
        #url = url_concat(self.userdata_url, self.userdata_params)

        #req = HTTPRequest(url,
        #                  method=self.userdata_method,
        #                  headers=headers,
        #                  )
        #resp = yield http_client.fetch(req)
        post_login_url = "http://35.185.43.84/api/auth/verify"
        my_req = HTTPRequest(post_login_url,
                          method = "GET",
                          headers = headers
                          )
        my_client = AsyncHTTPClient()
        post_resp = yield my_client.fetch(my_req, raise_error = False)
        post_resp_json = json.loads(post_resp.body.decode('utf8', 'replace'))

        with open("/tmp/post_resp_json.txt", "w") as ofh:
          ofh.write(json.dumps(post_resp_json))        

        resp_json = json.loads(resp.body.decode('utf8', 'replace'))
        dec_jwt = jwt.decode(access_token, verify = False)
        resp_json["username"] = dec_jwt["unique_name"]
        if not resp_json.get(self.username_key):
            self.log.error("OAuth user contains no key %s: %s", self.username_key, resp_json)
            return
        return {
            'name': resp_json.get(self.username_key),
            'auth_state': {
                'access_token': access_token,
                'oauth_user': resp_json,
            }
        }


class LocalGenericOAuthenticator(LocalAuthenticator, GenericOAuthenticator):

    """A version that mixes in local system user creation"""
    pass
