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
    return model.get_deps()

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
            self.is_set = True
            self.minOccurs = element.attrib["minOccurs"]
            if self.minOccurs == "unbounded":
                self.minOccurs = '"unboinded"'

        if "maxOccurs" in element.attrib:
            self.is_set = True
            self.maxOccurs = element.attrib["maxOccurs"]
            if self.maxOccurs == "unbounded":
                self.maxOccurs = '"unboinded"'

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
            if self.elType == "xs:string":
                ret += "%s = String" % self.name
            elif self.elType == "xs:boolean":
                ret += "%s = Boolean" % self.name
            elif self.elType == "xs:int" or self.elType == "xs:integer":
                ret += "%s = Integer" % self.name
            elif self.elType == "xs:long":
                ret += "%s = Long" % self.name
            elif self.elType == "xs:float":
                ret += "%s = Float" % self.name
            elif self.elType == "xs:double":
                ret += "%s = Double" % self.name
            elif self.elType == "xs:dateTime":
                ret += "%s = DateTime" % self.name
            else:
                print "TODO: unknown %s primitive type" % self.elType

        if params and ret:
            ret += "(" + ", ".join(params) + ")"

        return ret



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
            self.elements.append(Element(self, element))
        elif tag == "sequence":
            pass
        elif tag == "choice":
            new_options["choice"] = True
        elif tag == "group":
            pass
        elif tag == "complexType":
            pass
        elif tag == "attribute":
            pass
        else:
            print tag

        for child in element.iterchildren():
            self.visit_element(child, new_options)

    def get_deps(self):
        '''
        Return the list of depending model names
        '''
        return []



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
        self.requestType = requestType
        self.responseType = responseType

    def to_code(self):
        '''
        Convert operation to code
        '''
        return "operation_code\n"


def main(filename):
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

    # print models code
    for model in models:
        print model.to_code()

    ## print operations code
    #for operation in operationObjs:
        #print operation.to_code()

def help():
    print "usage:"
    print "%s <filename>" % sys.argv[0]
    sys.exit(0)

if __name__ == '__main__':
    if (len(sys.argv) != 2):
        help()
    main(sys.argv[1])