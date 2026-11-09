"""Review-only reuse of an existing ID when comma qualifiers match its actual Parent."""
from collections import defaultdict
from regional_matching import name_with_validated_parent,normalize


def qualified_rename_matches(source,path,targets):
    level=len(path)-1
    if level not in (2,3) or source.get('_parent')!=path[:-1]:return False
    if source.get('_blocked',True) or source.get('_requires_review',True):return False
    expected=targets[level-1].get(path[:-1])
    if not expected or source.get('Source_Parent_Id')!=expected:return False
    if level==3:
        city=targets[1].get(path[:2])
        if not city or source.get('Source_Direct_City_Id')!=city:return False
    base=name_with_validated_parent(source['Source_Name'],level,path[:-1])
    return bool(base and normalize(base,level)==normalize(path[-1],level))


def qualified_rename_groups(records,master_paths,targets):
    groups=[defaultdict(list) for _ in records]
    for level in (2,3):
        index=defaultdict(set)
        for path in master_paths[level]:index[(path[:-1],normalize(path[-1],level))].add(path)
        for source in records[level]:
            parent=source.get('_parent')
            base=name_with_validated_parent(source['Source_Name'],level,parent)
            if not base:continue
            paths=index.get((parent,normalize(base,level)),set())
            if len(paths)!=1:continue
            path=next(iter(paths))
            if qualified_rename_matches(source,path,targets):groups[level][path].append(source)
    return groups
