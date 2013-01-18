#!/usr/bin/env python

from lxml import etree
import sys

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

class TypeModel(object):
    '''
    Represents a type model. It parses the model tree, it's dependencies and
    generates the resulting source code.
    '''
    def __init__(self, element):
        pass

    def get_deps(self):
        return []

    def to_code(self):
        return "type_model_code\n"

def op_to_code(operation):
    '''
    Transforms an operation to source code
    '''
    return "operation_code\n"

def main(filename):
    '''
    Main function, parses the input file and generates the output code in stdout
    '''

    # some useful vars used in this function
    tree = etree.parse(filename)
    rootEl = tree.getroot()
    ns = {'d': 'http://schemas.xmlsoap.org/wsdl/',
        'xs': 'http://www.w3.org/2001/XMLSchema'}
    operations = rootEl.xpath("d:portType/d:operation", namespaces=ns)

    # list of models
    models = []

    # populates the model list, knowing there are two models per operation
    for operation in operations:
        opName = operation.values()[0]

        requestModelEl = rootEl.xpath(
            "d:types/xs:complexType[name='%sType']" % opName, namespaces=ns)
        responseModelEl = rootEl.xpath(
            "d:types/xs:complexType[name='%sResponseType']" % opName, namespaces=ns)

        models.append(TypeModel(requestModelEl))
        models.append(TypeModel(responseModelEl))

    # sort models by dependencies
    def get_deps(modelList, model):
        return model.get_deps()
    def is_equal(a, b):
        return str(a) == str(b)
    def list_objs(modelList):
        return modelList
    models = toposort(models, get_dependencies=get_deps, is_equal=is_equal, list_objs=list_objs)

    # print models code
    for model in models:
        print model.to_code()

    # print operations code
    for operation in operations:
        print op_to_code(operation)

def help():
    print "usage:"
    print "%s <filename>" % sys.argv[0]
    sys.exit(0)

if __name__ == '__main__':
    if (len(sys.argv) != 2):
        help()
    main(sys.argv[1])