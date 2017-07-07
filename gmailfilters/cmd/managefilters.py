from __future__ import absolute_import

import cliff.command
from copy import deepcopy
from lxml import etree
import argparse
import datetime
import sys
import yaml

NS_FEED = 'http://www.w3.org/2005/Atom'
NS_APP = 'http://schemas.google.com/apps/2006'

nsmap = {
    'app': NS_APP,
    None: NS_FEED,
}

querymap = {
    'app': NS_APP,
    'feed': NS_FEED,
}

# filter properties that we copy verbatim between XML and YAML.
# Basically, everything that is not a label.
basic_props = [
    'from',
    'to',
    'hasTheWord',
    'shouldArchive',
    'shouldMarkAsRead',
    'shouldNeverMarkAsImportant',
    'shouldNeverSpam',
    'shouldStar',
    'shouldTrash',
    'smartLabelToApply',
    'subject',
]

def same_condition(f1, f2):
    '''Deterine if two filters are identical.'''

    # This is used for coalescing labels.  If there aren't any labels
    # we can just bail out.
    if not ('label' in f1 and 'label' in f2):
        return False

    for prop in basic_props:
        inf1 = prop in f1
        inf2 = prop in f2
        if (inf1 and inf2) and not (f1[prop] == f2[prop]):
            return False
        elif (inf1 != inf2):
            return False

    return True


def to_prop_str(v):
    '''Convert booleans to lowercase strings, just convert everything
    else naively to strings.'''

    if isinstance(v, bool):
        return str(v).lower()
    else:
        return str(v)


class ManageFilters(cliff.command.Command):
    def get_parser(self, prog_name):
        p = super(ManageFilters, self).get_parser(prog_name)

        p.add_argument('--toxml',
                       action='store_true')
        p.add_argument('--fromxml',
                       dest='toxml',
                       action='store_false')
        p.add_argument('--output', '-o')
        p.add_argument('--no-collapse', '-n',
                       action='store_true')
        p.add_argument('input',
                       nargs='?')

        return p

    def take_action(self, args):
        if args.toxml:
            self.cmd_toxml(args)
        else:
            self.cmd_fromxml(args)

    def cmd_fromxml(self, args):
        with (sys.stdin if args.input is None else open(args.input)) as fd:
            doc = etree.parse(fd)

        filters = []
        for filter in doc.xpath('/feed:feed/feed:entry', namespaces=querymap):
            filterdict = {}
            for prop in filter.xpath('app:property', namespaces=querymap):
                if prop.get('name').startswith('size'):
                    continue

                filterdict[prop.get('name')] = prop.get('value')

            if filters and not args.no_collapse and same_condition(filterdict, filters[-1]):
                filters[-1]['label'] += ' %s' % filterdict['label']
            else:
                filters.append(filterdict)

        with (sys.stdout if args.output is None else open(args.output, 'w')) as fd:
            fd.write(yaml.dump(filters, default_flow_style=False))

    def cmd_toxml(self, args):
        with (sys.stdin if args.input is None else open(args.input)) as fd:
            filters = yaml.load(fd)

        doc = etree.Element('{%s}feed' % NS_FEED, nsmap=nsmap)
        title = etree.SubElement(doc, '{%s}title' % NS_FEED)
        title.text = 'Mail Filters'

        now = datetime.datetime.utcnow().isoformat()

        for filter in filters:
            entry = etree.Element('{%s}entry' % NS_FEED)
            title = etree.SubElement(entry, '{%s}title' % NS_FEED)
            title.text = 'Mail Filter'
            cat = etree.SubElement(entry, '{%s}category' % NS_FEED)
            cat.set('term', 'filter')
            updated = etree.SubElement(entry, '{%s}updated' % NS_FEED)
            updated.text = now
            cat = etree.SubElement(entry, '{%s}content' % NS_FEED)

            for propname in basic_props:
                if propname in filter:
                    prop = etree.SubElement(entry, '{%s}property' % NS_APP)
                    prop.set('name', propname)

                    # prop.set requires a string, so we call
                    # to_prop_str() to convert bools, ints, etc. to
                    # strings.
                    prop.set('value', to_prop_str(filter[propname]))

            if 'label' in filter:
                for label in filter['label'].split():
                    e = deepcopy(entry)
                    prop = etree.SubElement(e, '{%s}property' % NS_APP)
                    prop.set('name', 'label')
                    prop.set('value', label)
                    doc.append(e)
            else:
                doc.append(entry)

        with (sys.stdout if args.output is None else open(args.output, 'w')) as fd:
            fd.write(etree.tostring(doc, pretty_print=True))
