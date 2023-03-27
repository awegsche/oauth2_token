"""imap-oauth2 Entrypoint."""
import msal
import sys, os, atexit
import base64
import json
from argparse import ArgumentParser
from time import time

# cerntesting domain vern.ch
# use common is the app targeting also external users
AZURE_AUTHORITY = "https://login.microsoftonline.com/cern.ch"
# cern domain cern.ch
# use common is the app targeting also external users
AZURE_SCOPE = [
    "https://outlook.office.com/IMAP.AccessAsUser.All",
    "https://outlook.office.com/POP.AccessAsUser.All",
    "https://outlook.office.com/SMTP.Send",
]
IMAP_SERVER = "outlook.office365.com"
POP_SERVER = "outlook.office365.com"
SMTP_SERVER = "outlook.office365.com"


def main():
    parser = ArgumentParser()
    parser.add_argument("--smtp", action='store_true',help="smtp token (in base63 encoding)")
    parser.add_argument("--client", type=str, help="the client_id")
    parser.add_argument("--tf", type=str, help="tokenfile, where to store the obtained tokens")

    args = parser.parse_args()

    manager = TokenManager(args.client, args.tf)

    if args.smtp:
        manager.print_smtp_token()
    else:
        manager.print_token()


class TokenManager:
    def __init__(self, client_id, tokenfile):
        self.client_id = client_id
        self.tokenfile = tokenfile

        self.cache = msal.SerializableTokenCache()
        if os.path.exists(self.tokenfile):
            self.cache.deserialize(open(self.tokenfile, "r").read())

        atexit.register(
            lambda: open(self.tokenfile, "w").write(self.cache.serialize())
            # Hint: The following optional line persists only when state changed
            if self.cache.has_state_changed
            else None
        )

    def print_token(self) -> None:
        """Process bulk with imap-tools library"""
        # Authenticate to account using OAuth 2.0 mechanism
        access_token, username = self.get_access_token()
        #print(f"username:   {username}")
        print(access_token)
        #print(self.sasl_xoauth2(username, access_token))

    def print_smtp_token(self) -> None:
        """Process bulk with imap-tools library"""
        # Authenticate to account using OAuth 2.0 mechanism
        access_token, username = self.get_access_token()
        #print(f"username:   {username}")
        print(self.sasl_xoauth2(username, access_token, True))


    # not needed, right?
    def sasl_xoauth2(self, username, access_token, base64_encode=False) -> str:
        """Convert the access_token into XOAUTH2 format"""
        auth_string = "user=%s\1auth=Bearer %s\1\1" % (username, access_token)
        if base64_encode:
            auth_string = base64.b64encode(auth_string.encode("ascii")).decode("ascii")
        return auth_string

    def get_access_token(self) -> "tuple[str, str]":
        # Create a preferably long-lived app instance which maintains a token cache.
        app = msal.PublicClientApplication(
            self.client_id,
            authority=AZURE_AUTHORITY,
            token_cache=self.cache
            # token_cache=...  # Default cache is in memory only.
            # You can learn how to use SerializableTokenCache from
            # https://msal-python.rtfd.io/en/latest/#msal.SerializableTokenCache
        )

        result = None
        # Try to reload token from the cache
        accounts = app.get_accounts()
        if accounts:
            #print(accounts[0]["username"])
            result = app.acquire_token_silent(
                scopes=AZURE_SCOPE,
                account=accounts[0],
                authority=None,  # self.conf.AZURE_AUTHORITY,
                force_refresh=False,
                claims_challenge=None,
            )

        if not result:

            flow = app.initiate_device_flow(scopes=AZURE_SCOPE)
            if "user_code" not in flow:
                raise ValueError(
                    "Fail to create device flow. Err: %s" % json.dumps(flow, indent=4)
                )

            print(flow["message"])
            sys.stdout.flush()  # Some terminal needs this to ensure the message is shown

            # Ideally you should wait here, in order to save some unnecessary polling
            # input("Press Enter after signing in from another device to proceed, CTRL+C to abort.")

            result = app.acquire_token_by_device_flow(flow)  # By default it will block
            # You can follow this instruction to shorten the block time
            #    https://msal-python.readthedocs.io/en/latest/#msal.PublicClientApplication.acquire_token_by_device_flow
            # or you may even turn off the blocking behavior,
            # and then keep calling acquire_token_by_device_flow(flow) in your own customized loop.

        if "access_token" in result:
            # return the access token AND the username
            if not accounts:
                accounts = app.get_accounts()
            #print("Token aquired for:", accounts[0]["username"])
            #print("result", result)
            #if 'scope' in result:
            #    print('result["scope"]', result["scope"])
            # print('result["access_token"]', result["access_token"])
            return result["access_token"], accounts[0]["username"]
        else:
            raise ValueError(
                "Error getting access_token",
                result.get("error"),
                result.get("error_description"),
                result.get("correlation_id"),
            )


main()
