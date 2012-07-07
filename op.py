#!/usr/bin/env python
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from codecs import open
from ConfigParser import ConfigParser
from httplib2 import Http
from urllib import urlencode

import json
import os
import sys

__version__ = '0.1'


class ConfigError(Exception):
    pass


class ApiError(Exception):
    pass


class CommandError(Exception):
    pass


class HTTPError(Exception):

    def __init__(self, message, status_code=None, url=None):
        self.status_code = status_code
        self.url = url
        if self.status_code:
            message = 'Error %i: %s' % (self.status_code, message)
        if self.url:
            message += '; url=%s' % self.url
        Exception.__init__(self, message)


class Config(object):

    default_username = 'ownpaste'
    default_profile = 'default'

    def __init__(self, config_file, profile=None):
        self._cp = ConfigParser()
        read = self._cp.read(config_file)
        if not read:
            raise ConfigError('File not found: %r' % config_file)
        self.profile = profile
        if self.profile is None:
            self.profile = self.default_profile
            if self._cp.has_section('settings') and \
               self._cp.has_option('settings', 'default_profile'):
                self.profile = self._cp.get('settings', 'default_profile')
        if self.profile not in self.profiles:
            raise ConfigError('Invalid profile: %s' % self.profile)

    @property
    def profiles(self):
        return [i.split(':', 1)[1] for i in self._cp.sections() \
                if i.startswith('profile:')]

    @property
    def profile_section(self):
        return 'profile:%s' % self.profile

    @property
    def username(self):
        if not self._cp.has_option(self.profile_section, 'username'):
            return self.default_username
        return self._cp.get(self.profile_section, 'username')

    @property
    def password(self):
        if not self._cp.has_option(self.profile_section, 'password'):
            raise ConfigError('You should provide a password!')
        return self._cp.get(self.profile_section, 'password')

    @property
    def base_url(self):
        if not self._cp.has_option(self.profile_section, 'base_url'):
            raise ConfigError('You should provide the base URL of an ' \
                              'ownpaste server!')
        return self._cp.get(self.profile_section, 'base_url').rstrip('/')


class Session(object):

    def __init__(self, op_config):
        self.op_config = op_config
        self.http = Http(disable_ssl_certificate_validation=True)
        self.http.follow_all_redirects = True
        self.http.add_credentials(self.op_config.username,
                                  self.op_config.password)
        response = self.get('/')
        self.api_version = response.get('api_version')
        if self.api_version not in ['1']:
            raise HTTPError('Invalid API version: %s' % self.api_version)
        self.languages = response.get('languages', {})

    def request(self, method, url, data=None, params=None):
        data = data or {}
        params = params or {}
        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json',
                   'User-Agent': 'op/%s' % __version__}
        if 'language' in data:
            if data['language'] is not None \
               and data['language'] not in self.languages:
                raise HTTPError('Invalid language: %s' % data['language'])
        data = json.dumps(data)
        url = self.op_config.base_url + url.rstrip('/') + '/'
        query_string_params = {}
        for key, value in params.iteritems():
            if value is not None:
                query_string_params[key] = value
        if len(query_string_params):
            url += '?' + urlencode(query_string_params)
        response_headers, response = \
            self.http.request(url, method=method.upper(), body=data,
                              headers=headers)
        if response_headers['content-type'] != 'application/json':
            raise HTTPError('No application/json response found! Please ' \
                            'verify your ownpaste server URL!', url=url)
        try:
            data = json.loads(response)
        except ValueError:
            raise HTTPError('Failed to parse JSON response')
        if data['status'] == 'ok':
            return data
        raise HTTPError(data['error'],
                        status_code=int(response_headers['status']), url=url)

    def get(self, url, data=None, params=None):
        return self.request('GET', url, data, params)

    def post(self, url, data=None, params=None):
        return self.request('POST', url, data, params)

    def patch(self, url, data=None, params=None):
        return self.request('PATCH', url, data, params)

    def delete(self, url, data=None, params=None):
        return self.request('DELETE', url, data, params)


class ApiHandler(object):

    def __init__(self, config_file, profile):
        self.config = Config(config_file, profile=profile)
        self.session = Session(self.config)

    def post(self, file_content, file_name=None, language=None, private=False):
        return self.session.post('/paste/',
                                 data=dict(file_content=file_content,
                                           file_name=file_name,
                                           language=language,
                                           private=private))

    def patch(self, paste_id, file_content=None, file_name=None,
              language=None, private=None):
        return self.session.patch('/paste/%s/' % paste_id,
                                  data=dict(file_content=file_content,
                                            file_name=file_name,
                                            language=language,
                                            private=private))

    def delete(self, paste_id):
        try:
            return self.session.delete('/paste/%s/' % paste_id)
        except HTTPError, e:
            if e.status_code != 404:
                raise
            raise ApiError('Paste not found: %s' % paste_id)

    def get(self, paste_id):
        try:
            return self.session.get('/paste/%s/' % paste_id)
        except HTTPError, e:
            if e.status_code != 404:
                raise
            raise ApiError('Paste not found: %s' % paste_id)


class Commands(object):

    def input(self, file_name=None, content_required=True):
        name = None
        language = None
        content = None
        if file_name is None:
            if not sys.stdin.isatty():
                name = 'stdin'
                language = 'text'
                content = sys.stdin.read()
        else:
            if os.path.exists(file_name):
                name = file_name
                with open(file_name, 'r', encoding='utf-8') as fp:
                    content = fp.read()
            else:
                raise ApiError('file not found: %s' % file_name)
        if content_required and content is None:
            raise ApiError('No content to paste!')
        return name, language, content

    def output(self, content, raw_content=None):
        print >> sys.stdout, sys.stdout.isatty() and content or \
              (raw_content or content)

    def add(self, api, args):
        file_name, language, file_content = self.input(args.file)
        rv = api.post(file_content, args.file_name or file_name,
                      args.language or language, args.private)
        url = '%s/paste/%s/' % (api.config.base_url,
                                rv['private_id'] or rv['paste_id'])
        prefix = 'Paste: '
        if args.raw:
            prefix = 'Raw paste: '
            url += 'raw/'
        self.output(prefix + url, url)

    def get(self, api, args):
        rv = api.get(args.paste_id)
        if args.file is not None:
            with open(args.file, 'w', encoding='utf-8') as fp:
                fp.write(rv['file_content'])
            return
        sys.stdout.write(rv['file_content'])

    def modify(self, api, args):
        _, _, file_content = self.input(args.file, False)
        rv = api.patch(args.paste_id, file_content, args.file_name,
                      args.language, args.private)
        url = '%s/paste/%s/' % (api.config.base_url,
                                rv['private_id'] or rv['paste_id'])
        prefix = 'Paste: '
        if args.raw:
            prefix = 'Raw paste: '
            url += 'raw/'
        self.output(prefix + url, url)

    def delete(self, api, args):
        api.delete(args.paste_id)


def main():
    commands = Commands()

    parser = ArgumentParser(description='ownpaste client')
    parser.add_argument('-c', '--config-file', dest='config_file',
                        metavar='FILE', default=os.path.expanduser('~/.oprc'),
                        help="configuration file, overrides `~/.oprc'")
    parser.add_argument('-o', '--profile', dest='profile', metavar='PROFILE',
                        help="configuration profile, defaults to the " \
                        "[settings].default_profile value or `default'")

    actions = parser.add_subparsers(title='actions')

    add = actions.add_parser('add', help='add a paste')
    add.add_argument('-l', '--language', dest='language', metavar='LANG',
                     help='language alias')
    add.add_argument('-f', '--file-name', dest='file_name', metavar='FILENAME',
                     help='override file name')
    add.add_argument('-p', '--private', dest='private', action='store_true',
                     help='add paste as private')
    add.add_argument('-r', '--raw', dest='raw', action='store_true',
                     help='show link to raw paste, instead of HTML page')
    add.add_argument('file', nargs='?', metavar='FILE',
                     help='file to be pasted. defaults to STDIN')
    add.set_defaults(callback=commands.add)

    get = actions.add_parser('get', help='get a paste')
    get.add_argument('paste_id', metavar='PASTE_ID',
                     help='identifier of the paste to be fetched (public ' \
                     'or private)')
    get.add_argument('file', nargs='?', metavar='FILE',
                     help='save paste to file, instead of output to STDOUT')
    get.set_defaults(callback=commands.get)

    modify = actions.add_parser('modify', help='modify a paste')
    modify.add_argument('-l', '--language', dest='language', metavar='LANG',
                        help='modify language alias')
    modify.add_argument('-f', '--file-name', dest='file_name',
                        metavar='FILENAME', help='modify file name')
    public_or_private = modify.add_mutually_exclusive_group()
    public_or_private.add_argument('-p', '--private', dest='private',
                                   action='store_true',
                                   help='mark paste as private')
    public_or_private.add_argument('-u', '--public', dest='private',
                                   action='store_false',
                                   help='mark paste as public')
    modify.add_argument('-r', '--raw', dest='raw', action='store_true',
                     help='show link to raw paste, instead of HTML page')
    modify.add_argument('paste_id', metavar='PASTE_ID',
                        help='identifier of the paste to be modified ' \
                        '(public or private)')
    modify.add_argument('file', nargs='?', metavar='FILE',
                     help='file to be used as new content for the paste, ' \
                     'defaults to STDIN or nothing')
    modify.set_defaults(callback=commands.modify)

    delete = actions.add_parser('delete', help='delete a paste')
    delete.add_argument('paste_id', metavar='PASTE_ID',
                        help='identifier of the paste to be deleted (public ' \
                        'or private)')
    delete.set_defaults(callback=commands.delete)

    args = parser.parse_args()

    try:
        args.callback(ApiHandler(args.config_file, args.profile), args)
    except ApiError, e:
        print >> sys.stderr, '%s' % e
        return 2
    except Exception, e:
        print >> sys.stderr, '%s: %s' % (e.__class__.__name__, e)
        return 1


if __name__ == '__main__':
    sys.exit(main())
