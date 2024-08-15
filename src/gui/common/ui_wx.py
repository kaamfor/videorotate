
## Works on Windows and Sizers
def replaceWXItem(oldItem, newItem, **kwargs):
    sizer = oldItem.GetContainingSizer()
    
    sizer_child = [x.GetWindow() for x in sizer.GetChildren()]
    sizer_child_index = sizer_child.index(oldItem)
    
    if sizer_child_index != -1:
        sizer.Insert(sizer_child_index, newItem, **kwargs)
        
        sizer.Remove(sizer_child_index+1)
    else:
        sizer.Add(newItem, **kwargs)
    
    