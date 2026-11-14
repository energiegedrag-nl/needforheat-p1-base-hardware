"""Read a STEP assembly with names: returns list of (instance name, TopoDS_Shape located in global coords)."""
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.TopLoc import TopLoc_Location
from OCP.IFSelect import IFSelect_RetDone

def _name(lab):
    n = TDataStd_Name()
    return n.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), n) else "?"

def read(path):
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    r = STEPCAFControl_Reader(); r.SetNameMode(True)
    assert r.ReadFile(path) == IFSelect_RetDone
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    out = []
    def walk(lab, loc, path):
        if st.IsAssembly_s(lab):
            comps = TDF_LabelSequence(); st.GetComponents_s(lab, comps)
            for i in range(1, comps.Length() + 1):
                c = comps.Value(i)
                ref = TDF_Label(); st.GetReferredShape_s(c, ref)
                walk(ref, loc.Multiplied(st.GetLocation_s(c)), path + [_name(c)])
        else:
            out.append(("/".join(path + [_name(lab)]), st.GetShape_s(lab).Moved(loc)))
    roots = TDF_LabelSequence(); st.GetFreeShapes(roots)
    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), TopLoc_Location(), [])
    return out

if __name__ == "__main__":
    import sys
    for n, s in read(sys.argv[1])[:200]:
        print(n)
