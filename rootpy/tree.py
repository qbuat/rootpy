import re
import ROOT
from rootpy.basictypes import *
from rootpy.classfactory import *
from rootpy.core import *
from rootpy.utils import *
from rootpy.registry import *
from rootpy.io import *

class Tree(Plottable, Object, ROOT.TTree):
    """
    Inherits from TTree so all regular TTree methods are available
    but Draw has been overridden to improve usage in Python
    """
    draw_command = re.compile('^.+>>[\+]?(?P<name>[^(]+).*$')

    def __init__(self, buffer = None, variables = None, name = None, title = None):

        Object.__init__(self, name, title)
        if buffer != None:
            if variables == None:
                variables = buffer.keys()
            for variable in variables:
                value = buffer[variable]
                if isinstance(value, Variable):
                    self.Branch(variable, value, "%s/%s"% (name, value.type()))
                elif isinstance(value, ROOT.vector):
                    self.Branch(variable, value)
                else:
                    raise TypeError("type %s for branch %s is not valid"% (type(value), variable))

    def __iter__(self):

        i = 0
        while self.GetEntry(i):
            yield self
            i += 1
    
    def Draw(self, *args):
        """
        Draw a TTree with a selection as usual, but return the created histogram.
        """ 
        if len(args) == 0:
            raise TypeError("Draw did not receive any arguments")
        match = re.match(Tree.draw_command, args[0])
        histname = None
        if match:
            histname = match.group('name')
            hist_exists = ROOT.gDirectory.Get(histname) is not None
        ROOT.TTree.Draw(self, *args)
        if histname is not None:
            hist = asrootpy(ROOT.gDirectory.Get(histname))
            # if the hist already existed then I will
            # not overwrite its plottable features
            if not hist_exists:
                hist.decorate(self)
            return hist
        else:
            return None

register(Tree)

class TreeChain:
    """
    A replacement for TChain which does not play nice
    with addresses (at least on the Python side)
    """ 
    def __init__(self, treeName, files, buffer=None):
        
        self.treeName = treeName
        if type(files) is not list:
            files = [files]
        self.files = files
        self.buffer = buffer
        if self.buffer:
            for name, value in self.buffer.items():
                if name not in dir(self):
                    setattr(self, name, value)
                else:
                    raise ValueError("Illegal or duplicate branch name: %s"%name)
        self.weight = 1.
        self.tree = None
        self.file = None
        
    def __initialize(self):

        if self.tree != None:
            self.tree = None
        if self.file != None:
            self.file.Close()
            self.file = None
        if len(self.files) > 0:
            fileName = self.files.pop()
            self.file = File(fileName)
            if not self.file:
                print "WARNING: Skipping file. Could not open file %s"%(fileName)
                return self.__initialize()
            self.tree = self.file.Get(self.treeName)
            if not self.tree:
                print "WARNING: Skipping file. Tree %s does not exist in file %s"%(self.treeName, fileName)
                return self.__initialize()
            # Buggy D3PD:
            if len(self.tree.GetListOfBranches()) == 0:
                # Try the next file:
                print "WARNING: skipping tree with no branches in file %s"%fileName
                return self.__initialize()
            if self.buffer:
                self.tree.SetBranchStatus("*", False)
                for branch, address in self.buffer.items():
                    if not self.tree.GetBranch(branch):
                        print "WARNING: Skipping file. Branch %s was not found in tree %s in file %s"%(branch, self.treeName, fileName)
                        return self.__initialize()
                    self.tree.SetBranchStatus(branch, True)
                    self.tree.SetBranchAddress(branch, address)
            self.weight = self.tree.GetWeight()
            return True
        return False
    
    def __iter__(self):
        
        while self.__initialize():
            for entry in self.tree:
                yield self

class TreeBuffer(dict):
    """
    A dictionary mapping variable names ...
    """
    generate("vector<vector<float> >", "<vector>")
    generate("vector<vector<int> >", "<vector>")

    demote = {"Float_T":"F",
              "Int_T":"I",
              "Int":"I",
              "Float":"F",
              "F":"F",
              "I":"I",
              "UI":"UI",
              "vector<float>":"F",
              "vector<int>":"I",
              "vector<int, allocator<int> >":"I",
              "vector<float, allocator<float> >":"F",
              "VF":"F",
              "VI":"I",
              "vector<vector<float> >":"VF",
              "vector<vector<float> >":"VI",
              "vector<vector<int>, allocator<vector<int> > >":"VI",
              "vector<vector<float>, allocator<vector<float> > >":"VF",
              "VVF":"VF",
              "VVI":"VI"} 

    def __init__(self, variables, default = -1111, flatten = False):
        
        data = {}
        methods = dir(self)
        processed = []
        for name, vtype in variables:
            if flatten:
                vtype = TreeBuffer.demote[vtype]
            if name in processed:
                raise ValueError("Duplicate variable name %s"%name)
            else:
                processed.append(name)
            if vtype.upper() in ("I", "INT_T"):
                data[name] = Int(default)
            elif vtype.upper() in ("UI", "UINT_T"):
                data[name] = UInt(default)
            elif vtype.upper() in ("F", "FLOAT_T"):
                data[name] = Float(default)
            elif vtype.upper() in ("VI", "VECTOR<INT>"):
                data[name] = ROOT.vector("int")()
            elif vtype.upper() in ("VF", "VECTOR<FLOAT>"):
                data[name] = ROOT.vector("float")()
            elif vtype.upper() in ("VVI", "VECTOR<VECTOR<INT> >"):
                data[name] = ROOT.vector("vector<int>")()
            elif vtype.upper() in ("VVF", "VECTOR<VECTOR<FLOAT> >"):
                data[name] = ROOT.vector("vector<float>")()
            else:
                raise TypeError("Unsupported variable vtype: %s"%(vtype.upper()))
            if name not in methods and not name.startswith("_"):
                setattr(self, name, data[name])
            else:
                raise ValueError("Illegal variable name: %s"%name)
        dict.__init__(self, data)

    def reset(self):
        
        for value in self.values():
            value.clear()

    def __str__(self):

        return self.__repr__()

    def __repr__(self):

        rep = ""
        for var, value in self.items():
            rep += "%s ==> %s\n"%(var, value)
        return rep