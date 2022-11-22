# noinspection PyUnresolvedReferences
from ast import Dict
import orthanc
import os
import json
import re


CONFIG_LOADED = False
CALLED_AET_TO_PATH = None
ENABLED = False


def get_called_aet(dicom, instance_id):
    if dicom.GetInstanceOrigin() == orthanc.InstanceOrigin.DICOM_PROTOCOL:
        metadata = json.loads(orthanc.RestApiGet('/instances/%s/metadata?expand' % instance_id))
        if 'CalledAET' in metadata:
            callAet = str(metadata['CalledAET'])
            print('Got CalledAET %s (but returning %s)' % (callAet, callAet.upper()))
            return callAet.upper()
    return None


def delete_instance(instance_id):
    orthanc.RestApiDelete('/instances/%s' % instance_id)


def on_stored_instance(dicom, instance_id):
    global CONFIG_LOADED, CALLED_AET_TO_PATH, ENABLED
    if not CONFIG_LOADED:
        print('Loading radstore configuration...')
        radstore = json.loads(orthanc.GetConfiguration()).get('RadStore')
        CONFIG_LOADED = True

        ENABLED = bool(radstore['Enabled'])
        if ENABLED:
            CALLED_AET_TO_PATH = dict(radstore['CalledAETToPath'])
            if CALLED_AET_TO_PATH is None:
                raise 'Missing CalledAETToPath'
            print('Configuration loaded successfully')
        else:
            print('Configuration loaded successfully, RadStore plugin disabled')
    
    if not ENABLED:
        return
    
    print('radstore: on_stored_instance')

    called_aet = get_called_aet(dicom, instance_id)

    if called_aet is None:
        print('Warning: CalledAET was None for %s' % instance_id)
        return

    for match, path in CALLED_AET_TO_PATH.items():
        print('Matching \'%s\' against \'%s\'' % (match, called_aet))
        m = re.match(match, called_aet)
        if m:
            path = str(path)
            print('\'%s\' matched \'%s\' with the path %s' % (match, called_aet, path))

            path = path.replace('$1', called_aet)
            
            if not os.path.isdir(path):
                print('creating directory %s' % path)
                os.makedirs(path, exist_ok=True)

            dcm_file = os.path.join(path, "%s.dcm" % instance_id)

            print('Writing DICOM %s' % dcm_file)
            with open(dcm_file, "wb") as f:
                f.write(dicom.GetInstanceData())
            
            print('Successfully wrote DICOM file %s', dcm_file)

            delete_instance(instance_id)
            
            print('Sucessfully removed instance from Orthanc after writing it to the file %s' % dcm_file)

            break
        else:
            print('\'%s\' did not match \'%s\'', (match, called_aet))


orthanc.RegisterOnStoredInstanceCallback(on_stored_instance)