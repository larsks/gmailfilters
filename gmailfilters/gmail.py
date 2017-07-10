import httplib2
import os
import json
import logging
import googleapiclient
import googleapiclient.errors
import googleapiclient.discovery

from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

from gmailfilters import default

default_credentials_path = os.path.join(
        os.path.expanduser('~'), '.credentials', '{app_name}')

LOG = logging.getLogger('__name__')

class GmailClient(object):
    scopes = ' '.join([
        'https://www.googleapis.com/auth/gmail.settings.basic',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
    ])

    def __init__(self, app_name, client_id,
                 credentials_path=None,
                 credentials=None):
        self.app_name = app_name
        self.client_id = client_id
        self.credentials = credentials
        self.credentials_path = credentials_path

        self._service = None
        self._labels = None

        if self.credentials_path is None:
            self.credentials_path = default_credentials_path.format(
                app_name=self.app_name)

        cred_parent = os.path.dirname(self.credentials_path)

        if not os.path.isdir(cred_parent):
            os.makedirs(cred_parent)

        self.credentials_store = Storage(
            self.credentials_path)

        if self.credentials is None:
            self.credentials = self.credentials_store.get()

    def login(self):
        flow = client.flow_from_clientsecrets(self.client_id, self.scopes)
        flow.user_agent = self.app_name
        self.credentials = tools.run_flow(flow, self.credentials_store)

    def logout(self):
        self.credentials = None
        self.credentials_store.delete()
        self._service = None

    @property
    def service(self):
        if self._service is None:
            if not self.credentials or self.credentials.invalid:
                self.login()

            http = self.credentials.authorize(httplib2.Http())
            self._service = googleapiclient.discovery.build('gmail', 'v1', http=http)

        return self._service

    @property
    def labels(self):
        if self._labels is None:
            self._labels = {x['id']: x['name']
                            for x in self.get_labels()}

        return self._labels

    def get_labels(self):
        results = self.service.users().labels().list(
            userId='me').execute()
        return results.get('labels', [])

    def get_filters(self):
        results = self.service.users().settings().filters().list(
            userId='me').execute()
        return results.get('filter', [])

    def delete_all_filters(self):
        LOG.info('deleting all filters')
        res = []
        for filter in self.get_filters():
            res.append(self.delete_one_filter(filter['id']))

        return res

    def delete_one_filter(self, filterId):
        LOG.info('deleting filter %s', filterId)
        try:
            return self.service.users().settings().filters().delete(
                userId='me', id=filterId).execute()
        except googleapiclient.errors.HttpError as exc:
            if exc.resp.get('status', '') == '404':
                raise KeyError(filterId)
            else:
                raise

    def create_filter(self, filter):
        pass
