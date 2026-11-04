"""Read-only, plain-language parent instructions for each review candidate."""
from regional_matching import normalize

PARENT_REVIEW_FIELDS = {
    'Parent_Action_Note': 'Petunjuk_Perbaikan_Wilayah',
    'Parent_Action_Required': 'Perlu_Perbaikan_Wilayah',
}


def parent_action_note(source, path, target_ids, selected_id):
    """Use only verified parent IDs. Do not change source or canonical mapping.

    Instructions refer to the selected candidate's complete location. When its
    ID differs from the source, every instruction is conditional on choosing it.
    Missing parent IDs are explicitly left for checking, never guessed from names.
    """
    level=len(path)-1
    if level<1:
        return {'Parent_Action_Note':'','Parent_Action_Required':''}
    labels={0:'provinsi',1:'kabupaten/kota',2:'kecamatan'}
    relations=[(level-1,path[:-1],source.get('Source_Parent_Id',''))]
    if level==3:
        relations.append((1,path[:2],source.get('Source_Direct_City_Id','')))
    actions=[];correct=[]
    for parent_level,parent,current in relations:
        name=parent[-1];label=labels[parent_level]
        expected=target_ids[parent_level].get(parent,'')
        current=str(current or '').strip()
        if expected and current==expected:
            if parent_level==1:
                display=('Kabupaten '+name[5:] if name.startswith('Kab. ') else name)
            else:
                display=label.capitalize()+' '+name
            correct.append(display+' sudah sesuai.')
        elif expected:
            verb='Lengkapi' if current in {'','0'} else 'Ubah'
            prep='dengan' if verb=='Lengkapi' else 'menjadi'
            actions.append(f'{verb} {label} {prep} {name}, ID {expected}.')
        else:
            actions.append(f'Pastikan {label} {name}. ID untuk wilayah ini belum dapat dipastikan; periksa sebelum mengisi atau mengubahnya.')
    same=(selected_id==source['Source_Id']
          and normalize(source['Source_Name'],level)==normalize(path[-1],level))
    if actions:
        title='Setelah client memastikan lokasi:' if same else 'Jika rekomendasi ini dipilih setelah client memastikan lokasi:'
        steps=actions+correct+(['Gunakan ID sumber yang sama.'] if same else [])
    else:
        title='Hubungan wilayah untuk lokasi rekomendasi:'
        steps=correct+['Tidak perlu mengubah hubungan wilayah.']
    return {'Parent_Action_Note':title+'\n'+'\n'.join('• '+step for step in steps),
            'Parent_Action_Required':'YES' if actions else 'NO'}
