"""Cisco vManage Templates Methods.
"""

import dictdiffer
from vmanage.api.feature_templates import FeatureTemplates
from vmanage.api.device_templates import DeviceTemplates
from vmanage.api.utilities import Utilities
from vmanage.api.device import Device
from vmanage.api.local_policy import LocalPolicy


class TemplateData(object):
    """vManage Device Methods

    Responsible vManage Device Templates.

    """
    def __init__(self, session, host, port=443):
        """Initialize Templates Method object with session parameters.

        Args:
            session (obj): Requests Session object
            host (str): hostname or IP address of vManage
            port (int): default HTTPS 443

        """

        self.session = session
        self.host = host
        self.port = port
        self.base_url = f'https://{self.host}:{self.port}/dataservice/'
        self.device_templates = DeviceTemplates(self.session, self.host, self.port)
        self.feature_templates = FeatureTemplates(self.session, self.host, self.port)

    def convert_device_template_to_name(self, device_template):
        """Convert a device template components from IDs to Names.

        Args:
            device_template (dict): Device Template

        Returns:
            result (dict): Converted Device Template.
        """

        feature_template_dict = self.feature_templates.get_feature_template_dict(factory_default=True,
                                                                                 key_name='templateId')

        if 'policyId' in device_template and device_template['policyId']:
            policy_id = device_template['policyId']
            vmanage_local_policy = LocalPolicy(self.session, self.host, self.port)
            local_policy_dict = vmanage_local_policy.get_local_policy_dict(key_name='policyId')
            if policy_id in list(local_policy_dict.keys()):
                device_template['policyName'] = local_policy_dict[policy_id]['policyName']
            else:
                raise Exception(f"Could not find local policy {policy_id}")

        if 'generalTemplates' in device_template:
            generalTemplates = []
            for old_template in device_template.pop('generalTemplates'):
                new_template = {
                    'templateName': feature_template_dict[old_template['templateId']]['templateName'],
                    'templateType': old_template['templateType']
                }
                if 'subTemplates' in old_template:
                    subTemplates = []
                    for sub_template in old_template['subTemplates']:
                        subTemplates.append({
                            'templateName':
                            feature_template_dict[sub_template['templateId']]['templateName'],
                            'templateType':
                            sub_template['templateType']
                        })
                    new_template['subTemplates'] = subTemplates
                generalTemplates.append(new_template)
            device_template['generalTemplates'] = generalTemplates

        return device_template

    def convert_device_template_to_id(self, device_template):
        """Convert a device template components from Names to IDs.

        Args:
            device_template (dict): Device Template

        Returns:
            result (dict): Converted Device Template.
        """

        if 'PolicyName' in device_template:
            vmanage_local_policy = LocalPolicy(self.session, self.host, self.port)
            local_policy_dict = vmanage_local_policy.get_local_policy_dict(key_name='policyId')
            if device_template['PolicyName'] in local_policy_dict:
                device_template['PolicyId'] = local_policy_dict[device_template['PolicyName']]['PolicyId']
                device_template.pop('PolicyName')
            else:
                raise Exception(f"Could not find local policy {device_template['PolicyName']}")

        if 'generalTemplates' in device_template:
            device_template['generalTemplates'] = self.generalTemplates_to_id(device_template['generalTemplates'])

        return device_template

    def generalTemplates_to_id(self, generalTemplates):
        converted_generalTemplates = []
        feature_templates = self.feature_templates.get_feature_template_dict(factory_default=True)
        for template in generalTemplates:
            if 'templateName' not in template:
                self.result['generalTemplates'] = generalTemplates
                self.fail_json(msg="Bad template")
            if template['templateName'] in feature_templates:
                template_item = {
                    'templateId': feature_templates[template['templateName']]['templateId'],
                    'templateType': template['templateType']
                }
                if 'subTemplates' in template:
                    subTemplates = []
                    for sub_template in template['subTemplates']:
                        if sub_template['templateName'] in feature_templates:
                            subTemplates.append({
                                'templateId':
                                feature_templates[sub_template['templateName']]['templateId'],
                                'templateType':
                                sub_template['templateType']
                            })
                        else:
                            self.fail_json(msg="There is no existing feature template named {0}".format(
                                sub_template['templateName']))
                    template_item['subTemplates'] = subTemplates

                converted_generalTemplates.append(template_item)
            else:
                self.fail_json(msg="There is no existing feature template named {0}".format(template['templateName']))

        return converted_generalTemplates

    def import_feature_template_list(self, feature_template_list, check_mode=False, update=False):
        """Add a list of feature templates to vManage.


        Args:
            check_mode (bool): Only check to see if changes would be made
            update (bool): Update the template if it exists

        Returns:
            result (list): Returns the diffs of the updates.

        """
        # Process the feature templates
        feature_template_updates = []
        feature_template_dict = self.feature_templates.get_feature_template_dict(factory_default=True, remove_key=False)
        for feature_template in feature_template_list:
            if feature_template['templateName'] in feature_template_dict:
                existing_template = feature_template_dict[feature_template['templateName']]
                feature_template['templateId'] = existing_template['templateId']
                diff = list(
                    dictdiffer.diff(existing_template['templateDefinition'], feature_template['templateDefinition']))
                if len(diff):
                    feature_template_updates.append({'name': feature_template['templateName'], 'diff': diff})
                    if not check_mode and update:
                        self.feature_templates.update_feature_template(feature_template)
            else:
                diff = list(dictdiffer.diff({}, feature_template['templateDefinition']))
                feature_template_updates.append({'name': feature_template['templateName'], 'diff': diff})
                if not check_mode:
                    self.feature_templates.add_feature_template(feature_template)

        return feature_template_updates

    def export_device_template_list(self, factory_default=False, name_list=None):
        """Export the list of device templates.

        Args:
            factory_default (bool): Include factory default
            name_list (list of strings): A list of template names to retreive.

        Returns:
            result (dict): All data associated with a response.
        """
        if name_list is None:
            name_list = []
        device_template_list = self.device_templates.get_device_templates()
        return_list = []

        #pylint: disable=too-many-nested-blocks
        for device_template in device_template_list:
            # If there is a list of template name, only return the ones asked for.
            # Otherwise, return them all
            if name_list and device_template['templateName'] not in name_list:
                continue
            obj = self.device_templates.get_device_template_object(device_template['templateId'])
            if obj:
                if not factory_default and obj['factoryDefault']:
                    continue
                obj['templateId'] = device_template['templateId']

                # obj['attached_devices'] = self.get_template_attachments(device['templateId'])
                # obj['input'] = self.get_template_input(device['templateId'])
                converted_device_template = self.convert_device_template_to_name(obj)
                return_list.append(converted_device_template)
        return return_list

    def import_device_template_list(self, device_template_list, check_mode=False, update=False):
        """Add a list of feature templates to vManage.


        Args:
            check_mode (bool): Only check to see if changes would be made
            update (bool): Update the template if it exists

        Returns:
            result (list): Returns the diffs of the updates.

        """
        device_template_updates = []
        device_template_dict = self.device_templates.get_device_template_dict()
        for device_template in device_template_list:
            if device_template['templateName'] in device_template_dict:
                existing_template = self.convert_device_template_to_name(
                    device_template_dict[device_template['templateName']])
                if 'generalTemplates' in device_template:
                    diff = list(
                        dictdiffer.diff(existing_template['generalTemplates'], device_template['generalTemplates']))
                elif 'templateConfiguration' in device_template:
                    diff = list(
                        dictdiffer.diff(existing_template['templateConfiguration'],
                                        device_template['templateConfiguration']))
                else:
                    raise Exception("Template {0} is of unknown type".format(device_template['templateName']))
                if len(diff):
                    device_template_updates.append({'name': device_template['templateName'], 'diff': diff})
                    if not check_mode and update:
                        if not check_mode:
                            converted_device_template = self.convert_device_template_to_id(device_template)
                            self.update_device_template(converted_device_template)
            else:
                if 'generalTemplates' in device_template:
                    diff = list(dictdiffer.diff({}, device_template['generalTemplates']))
                elif 'templateConfiguration' in device_template:
                    diff = list(dictdiffer.diff({}, device_template['templateConfiguration']))
                else:
                    raise Exception("Template {0} is of unknown type".format(device_template['templateName']))
                device_template_updates.append({'name': device_template['templateName'], 'diff': diff})
                if not check_mode:
                    converted_device_template = self.convert_device_template_to_id(device_template)
                    self.add_device_template(converted_device_template)

        return device_template_updates

    def import_attachment_list(self, attachment_list, check_mode=False, update=False):
        """Import a list of device attachments to vManage.


        Args:
            check_mode (bool): Only check to see if changes would be made
            update (bool): Update the template if it exists

        Returns:
            result (list): Returns the diffs of the updates.

        """
        attachment_updates = {}
        attachment_failures = {}
        action_id_list = []
        device_template_dict = self.device_templates.get_device_template_dict()
        vmanage_device = Device(self.session, self.host, self.port)
        for attachment in attachment_list:
            if attachment['template'] in device_template_dict:
                if attachment['device_type'] == 'vedge':
                    # The UUID is fixes from the serial file/upload
                    device_uuid = attachment['uuid']
                else:
                    # If this is not a vedge, we need to get the UUID from the vmanage since
                    # it is generated by that vmanage
                    device_status = vmanage_device.get_device_status(attachment['host_name'], key='host-name')
                    if device_status:
                        device_uuid = device_status['uuid']
                    else:
                        raise Exception(f"Cannot find UUID for {attachment['host_name']}")

                template_id = device_template_dict[attachment['template']]['templateId']
                attached_uuid_list = self.device_templates.get_attachments(template_id, key='uuid')
                if device_uuid in attached_uuid_list:
                    # The device is already attached to the template.  We need to see if any of
                    # the input changed, so we make an API call to get the input on last attach
                    existing_template_input = self.device_templates.get_template_input(
                        device_template_dict[attachment['template']]['templateId'], [device_uuid])
                    current_variables = existing_template_input['data'][0]
                    changed = False
                    for property_name in attachment['variables']:
                        # Check to see if any of the passed in varibles have changed from what is
                        # already on the attachment.  We are are not checking to see if the
                        # correct variables are here.  That will be done on attachment.
                        if ((property_name in current_variables) and
                            (str(attachment['variables'][property_name]) != str(current_variables[property_name]))):
                            changed = True
                    if changed:
                        if not check_mode and update:
                            action_id = self.attach_to_template(template_id, device_uuid, attachment['system_ip'],
                                                                attachment['host_name'], attachment['site_id'],
                                                                attachment['variables'])
                            action_id_list.append(action_id)
                else:
                    if not check_mode:
                        action_id = self.attach_to_template(template_id, device_uuid, attachment['system_ip'],
                                                            attachment['host_name'], attachment['site_id'],
                                                            attachment['variables'])
                        action_id_list.append(action_id)
            else:
                raise Exception(f"No template named Template {attachment['templateName']}")

        # pp = pprint.PrettyPrinter(indent=2)
        utilities = Utilities(self.session, self.host)
        # Batch the waits so that the peocessing of the attachments is in parallel
        for action_id in action_id_list:
            result = utilities.waitfor_action_completion(action_id)
            data = result['action_response']['data'][0]
            # pp.pprint(data)
            if result['action_status'] == 'failure':
                attachment_failures.update({data['uuid']: data['currentActivity']})
            else:
                attachment_updates.update({data['uuid']: data['currentActivity']})

        result = {'updates': attachment_updates, 'failures': attachment_failures}
        return result