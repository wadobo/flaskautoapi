#!/usr/bin/env python

from lxml import etree
import sys

NAMESPACE = "wadobo.api"

def toposort(objs, get_dependencies=lambda objs, i: objs[i],
        is_equal=lambda a,b: a==b,
        list_objs=lambda objs: objs.keys()):
    '''
    Topological sort

    Example:
        In [10]: deps = {
    ....:     '1': ['2', '3'],
    ....:     '2': ['4'],
    ....:     '3': [],
    ....:     '4': ['6', '3'],
    ....:     '5': [],
    ....:     '6': []
    ....: }

        In [11]: toposort(deps)
        Out[11]: ['6', '5', '3', '4', '2', '1']
    '''

    ret = []
    def has_unmet_deps(i):
        '''
        Returns True if it has unmet dependencies
        '''
        for dep in get_dependencies(objs, i):
            if dep not in ret:
                return True
        return False

    queue = [i for i in list_objs(objs) if not get_dependencies(objs, i)]
    while queue:
        obj = queue.pop()
        ret.append(obj)
        for obj2 in list_objs(objs):
            if not has_unmet_deps(obj2) and obj2 not in queue and obj2 not in ret:
                queue.append(obj2)
    return ret


# 4 functions used to sort models by dependencies and other model related things
def get_deps(modelList, model):
    depnames = model.get_deps()
    deps = [i for i in modelList if i.name in depnames]
    return deps

def is_equal(a, b):
    return str(a) == str(b)

def list_objs(modelList):
    return modelList

def contains(modelList, a):
    for i in modelList:
        if is_equal(i, a):
            return True
    return False



def get_simplified_tag(element):
    '''
    Gets the simplified element tag
    '''
    if '}' in element.tag:
        return element.tag.split('}')[1]
    else:
        return element.tag


class Element(object):
    '''
    Represents an xs:Element. Used for parsing and code translation
    '''
    # xml DOM element representing this object
    element = None

    # parent dom 
    parent = None


    # attributes used in code generation #

    is_set = False
    is_complex_type = False
    is_empty_type = False
    minOccurs = None
    maxOccurs = None

    name = ""
    elType = ""

    def __init__(self, parent, element):
        self.element = element
        self.parent = parent

        # global vars set in main
        global models
        global rootEl
        global ns

        # parse element for latter on be able to generate code
        self.elType = element.attrib["type"]
        elName = get_simplified_tag(element)
        self.name = element.attrib["name"]

        if self.elType.startswith("tns:"):
            self.elType = self.elType.split(':')[1]
            self.parent.dependencies.append(self.elType)

            if self.elType == "EmptyElementType":
                self.is_empty_type = True
                return

            self.is_complex_type = True

            if not contains(models, self.elType):
                new_type = rootEl.xpath(
                    "d:types/xs:schema/xs:complexType[@name='%s']" % self.elType,
                    namespaces=ns)[0]
                models.append(TypeModel(new_type, self.elType))

        if "minOccurs" in element.attrib:
            self.minOccurs = element.attrib["minOccurs"]
            if self.minOccurs == "unbounded":
                self.is_set = True
                self.minOccurs = '"unbounded"'
            else:
                if int(self.minOccurs) > 1:
                    self.is_set = True

        if "maxOccurs" in element.attrib:
            self.is_set = True
            self.maxOccurs = element.attrib["maxOccurs"]
            if self.maxOccurs == "unbounded":
                self.maxOccurs = '"unbounded"'

    def elem_type(self):
        '''
        Returns the type class
        '''

        mapping = {
            'xs:string': 'String',
            'xs:boolean': 'Boolean',
            'xs:int': 'Integer',
            'xs:integer': 'Integer',
            'xs:long': 'Long',
            'xs:float': 'Float',
            'xs:double': 'Double',
            'xs:dateTime': 'DateTime',
        }

        ret = ""
        if not self.is_complex_type:
            ret = mapping.get(self.elType, '')
            if not ret:
                print "TODO: unknown %s primitive type" % self.elType
        else:
            ret = self.elType

        return ret

    def to_code(self):
        '''
        Generates code!
        '''
        # This case is handled in TypeModel specifically
        if self.is_empty_type:
            return ""

        ret = ""
        params = []

        if not self.is_complex_type:
            if self.minOccurs:
                params.append("min_occurs=" + self.minOccurs)

            if self.maxOccurs:
                params.append("max_occurs=" + self.maxOccurs)

            ret += "%s = %s" % (self.name, self.elem_type())

            if params and ret:
                ret += "(" + ", ".join(params) + ")"

        if self.is_complex_type:
            if not self.is_set:
                ret += "%(name)s = %(type_name)s" % dict(name=self.name,
                    type_name=self.elType)
                if self.minOccurs:
                    ret += "(min_occurs=%s)" % self.minOccurs
            else:
                ret += "%s = Array" % self.name

                params = [self.elType]

                if self.minOccurs:
                    params.append("min_occurs=" + self.minOccurs)

                if self.maxOccurs:
                    params.append("max_occurs=" + self.maxOccurs)

                ret += "(" + ", ".join(params) + ")"


        return ret


class Group(object):
    '''
    Represents a group, used for parsing and generating code
    '''

    # possible values in this attribute
    values = []

    def __init__(self, element):
        '''
        Constructor, does the parsing
        '''
        # global
        global models
        global rootEl
        global ns

        ref = element.attrib["ref"].split("tns:")[1]
        self.values = rootEl.xpath(
            "d:types/xs:schema/xs:group[@name='%s']//xs:element/@name" % ref,
            namespaces=ns)

    def to_code(self):
        '''
        Generates code!
        '''
        return 'Attribute = String(pattern="(%s)")' % '|'.join(self.values)


class Attribute(object):
    '''
    Represents an attribute, used for parsing and code generation
    '''

    name = ""

    def __init__(self, element):
        '''
        Constructor, does the parsing
        '''
        self.name = element.attrib["name"]
        self.fixed_value = element.attrib["fixed"]

    def to_code(self):
        '''
        Generates code!
        '''
        return '%(name)s = Mandatory.String(pattern="%(fixed_value)s")' % dict(
            name=self.name, fixed_value=self.fixed_value)


class TypeModel(object):
    '''
    Represents a type model. It parses the model tree, it's dependencies and
    generates the resulting source code.
    '''

    # Name of the model
    name = ""
    dependencies = []
    elements = []

    def __init__(self, element, name):
        '''
        constructor of the model. parses the model xml tree
        '''
        self.name = name
        self.dependencies = []
        self.elements = []

        # does the parsing using the visitor pattern
        self.visit_element(element)

    def visit_element(self, element, options=dict(depth=0)):
        '''
        Parses the element tree
        '''
        # global 
        global models
        global rootEl
        global ns
        tag = get_simplified_tag(element)
        new_options = options.copy()
        new_options["depth"] += 1

        if tag == "element":
            el = Element(self, element)
            self.elements.append(el)

            if el.is_complex_type and el.elType == "AssignPrivateIpAddressesSetRequestType":
                self.dependencies.append(el.elType)
        elif tag == "sequence":
            pass
        elif tag == "choice":
            pass
        elif tag == "group":
            self.elements.append(Group(element))
        elif tag == "complexType":
            pass
        elif tag == "attribute":
            self.elements.append(Attribute(element))
        else:
            print tag

        for child in element.iterchildren():
            self.visit_element(child, new_options)

    def get_deps(self):
        '''
        Return the list of depending model names
        '''
        return self.dependencies



    def to_code(self):
        '''
        Generates code!
        '''
        ret = "class %(name)s(ComplexModel):\n    __namespace__ = '%(ns)s'\n\n    " %\
            dict(name=self.name, ns=NAMESPACE)

        ret += "\n    ".join([e.to_code() for e in self.elements]) + "\n"

        return ret

    def __str__(self):
        '''
        returns the name of the model
        '''
        return self.name

class Operation(object):
    '''
    Represents an operation
    '''

    def __init__(self, element, requestType, responseType):
        self.element = element
        self.name = self.element.attrib['name']
        self.requestType = requestType
        self.responseType = responseType

    def to_code(self):
        '''
        Convert operation to code
        '''

        request = [i for i in models if i.name == self.requestType]
        if not request:
            return "# %s NOT IMPLEMENTED (because can't find %s)" % (self.name, self.requestType)
        request = request[0]

        response = [i for i in models if i.name == self.responseType]
        if not response:
            return "# %s NOT IMPLEMENTED (because can't find %s)" % (self.name, self.responseType)
        response = response[0]

        template = '''
class {name}Service(ServiceBase):
    @srpc({request_types}, _returns={response})
    def {name}({request_attrs}):
        req = {request}({request_named_attrs})

        resp = {response}()
        return resp
'''
        tmpl = template.format(name=self.name,
                             request=self.requestType,
                             request_types=', '.join(i.elem_type() for i in request.elements if isinstance(i, Element)),
                             request_attrs=', '.join(i.name for i in request.elements if isinstance(i, Element)),
                             request_named_attrs=', '.join('{0}={0}'.format(i.name) for i in request.elements if isinstance(i, Element)),
                             response=self.responseType)

        return tmpl


def main(filename, ops=True, types=True):
    '''
    Main function, parses the input file and generates the output code in stdout
    '''
    global rootEl
    global models
    global ns

    # some useful vars used in this function
    tree = etree.parse(filename)

    rootEl = tree.getroot()
    ns = {'d': 'http://schemas.xmlsoap.org/wsdl/',
        'xs': 'http://www.w3.org/2001/XMLSchema'}
    operations = rootEl.xpath("d:portType/d:operation", namespaces=ns)

    # list of models
    models = []

    operationObjs = []

    # populates the model list, knowing there are two models per operation
    for operation in operations:
        opName = operation.values()[0]

        element = rootEl.xpath(
            "d:types/xs:schema/xs:element[@name='%s']" % opName, namespaces=ns)[0]
        req_name = element.attrib["type"].split("tns:")[1]
        requestModelEl = rootEl.xpath(
            "d:types/xs:schema/xs:complexType[@name='%s']" % req_name, namespaces=ns)[0]
        # model might be already there
        if not contains(models, req_name):
            models.append(TypeModel(requestModelEl, req_name))

        element = rootEl.xpath(
            "d:types/xs:schema/xs:element[@name='%sResponse']" % opName, namespaces=ns)[0]
        resp_name = element.attrib["type"].split("tns:")[1]
        responseModelEl = rootEl.xpath(
            "d:types/xs:schema/xs:complexType[@name='%s']" % resp_name, namespaces=ns)[0]
        if not contains(models, resp_name):
            models.append(TypeModel(responseModelEl, resp_name))

        operationObjs.append(Operation(operation, req_name, resp_name))

    models = toposort(models, get_dependencies=get_deps, is_equal=is_equal, list_objs=list_objs)

    if types:
        # print models code
        for model in models:
            print model.to_code()

    if ops:
        # print operations code
        for operation in operationObjs:
            print operation.to_code()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Parses a wsdl file and generates spyne code.')
    parser.add_argument('filename', metavar='filename.wsdl', type=str,
                       help='The wsdl definition filename')
    parser.add_argument('--operations', '-o', dest='types',
                        action='store_false',
                        help='Only generates operations')
    parser.add_argument('--types', '-t', dest='ops',
                        action='store_false',
                        help='Only generates types')

    args = parser.parse_args()

    main(args.filename, args.ops, args.types)
