#!/usr/bin/env python

import sys
import re


H4 = re.compile(r"====([\w /]+)====")
H3 = re.compile(r"===([\w /]+)===")
END = re.compile(r"^=.*")
HTTP = re.compile(r" \* (?P<method>POST|GET|PUT|DELETE) (?P<path>.*)")
ADMIN = re.compile(r" \* Admin only")
PARAM_END = re.compile(r"^ \* .*")
URL_PARAMS = re.compile(r"<([\w_-]*)>")


class Resource:
    def __init__(self):
        self.admin = False
        self.method = "POST"
        self.path = "/"
        self.params = []
        self.filters = []
        self.optional = []
        self.doc = []
        self.name = "nonamed"
        self.group = "none"

    def parse_something(self, lines, i, container):
        i = i + 1
        while i < len(lines):
            line = lines[i].strip()
            match = END.match(line)
            if match:
                break
            match = PARAM_END.match(lines[i])
            if match:
                break

            if line.strip():
                self.doc.append(lines[i])
            # removing * 
            line = line[2:]
            arg = re.split(r'[: \.=]', line)[0]
            if arg.strip():
                container.append(arg)
            i = i + 1
        return i

    def parse_optional(self, lines, i):
        return self.parse_something(lines, i, self.optional)

    def parse_params(self, lines, i):
        return self.parse_something(lines, i, self.params)

    def parse_filters(self, lines, i):
        return self.parse_something(lines, i, self.filters)

    def __str__(self):
        return "%s: %s - %s" % (self.name, self.method, self.path)

    def to_code(self):
        args = URL_PARAMS.findall(self.path)
        req = 'request.form' if self.method in ['POST', 'PUT'] else 'request.args'

        params = ""
        optional = ""
        filters = ""

        if self.params:
            params = '''
    params = [%(params)s]
    data = dict((p, %(req)s.get(p)) for p in params)
    if None in data.values():
        raise abort(400)
''' % { 'params': ', '.join(repr(i) for i in self.params), 'req': req, }

        if self.optional:
            optional = '''
    optional = [%(opt)s]
    data.update(dict((p, %(req)s.get(p)) for p in optional))
''' % { 'opt': ', '.join(repr(i) for i in self.optional), 'req': req, }

        if self.filters:
            filters = '''
    filters = [%(filters)s]
    filters = dict((p, request.args.get(p)) for p in filters)
''' % { 'filters': ', '.join(repr(i) for i in self.filters), 'req': req, }

        code = '''

@app.route('%(path)s', methods=['%(method)s'])
def %(name)s(%(args)s):
    """
%(doc)s
    """

    data = {}
    filters = {}
''' % {
            'path': self.path,
            'method': self.method,
            'name': unify(self.group) + '_' + self.name,
            'args': ', '.join(args),
            'doc': ''.join(self.doc),
        }

        if params:
            code += params

        if optional:
            code += optional

        if filters:
            code += filters


        realpath = repr(URL_PARAMS.sub(r'%s', self.path))
        if args:
            realpath = "%s %% (%s, )" % (realpath, ', '.join(args))

        code += '''
    return internal_call(%(path)s, '%(method)s',
                         data=data, filters=filters)
''' % {
        'path': realpath,
        'method': self.method,
      }

        return code



def unify(name):
    name = name.strip().lower().replace(" ", "_").replace("/", "_")
    return name


def parse_resource(group, lines, i, match, container):
    resource_name = match.groups()[0]
    resource_name = unify(resource_name)
    r = Resource()
    r.group = group
    r.name = resource_name

    i += 1
    while i < len(lines):
        line = lines[i]
        match = END.match(line)
        if match:
            break

        if line.strip():
            r.doc.append(line)

        # admin only
        match = ADMIN.match(line)
        if match:
            r.admin = True

        # method and path
        match = HTTP.match(line)
        if match:
            r.method = match.group("method")
            r.path = match.group("path")

        l = line.lower()

        # optional parameters
        if "optional" in l or "extra" in l:
            i = r.parse_optional(lines, i)
            continue

        # parameters
        if "parameter" in l:
            i = r.parse_params(lines, i)
            continue

        # filters
        if "filter" in l:
            i = r.parse_filters(lines, i)
            continue

        i += 1

    container.append(r)
    return i


def load_resources(filename):
    resources = []
    with open(filename) as f:
        group = ""

        lines = f.readlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            match = H4.match(line)
            if match:
                i = parse_resource(group, lines, i, match, resources)
                continue

            match = H3.match(line)
            if match:
                group = match.groups()[0]
                group = group.strip()

            i += 1

    return resources


def main(filename):
    resources = load_resources(filename)

    prevgroup = ""
    for r in resources:
        if r.group != prevgroup:
            prevgroup = r.group
            print "# %s" % r.group.upper()

        if r.admin:
            continue

        print "%s" % r.to_code()

    # resources to unify
    while resources:
        first = resources.pop()
        similars = []
        for r in resources:
            if r.path == first.path and r.method == first.method:
                similars.append(r)

        for i in similars:
            resources.remove(i)

        similars.append(first)
        if len(similars) > 1:
            print "\n# Similars:"
            for i in similars:
                n = unify(i.group) + '_' + i.name
                print "# %s" % n


def help():
    print "usage:"
    print "%s <filename>" % sys.argv[0]
    sys.exit(0)


if __name__ == '__main__':
    if (len(sys.argv) != 2):
        help()
    main(sys.argv[1])
