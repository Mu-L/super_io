import bpy
from .. import __folder_name__
from bpy.props import CollectionProperty

import time
import os


def get_pref():
    """get preferences of this plugin"""
    return bpy.context.preferences.addons.get(__folder_name__).preferences


class MeasureTime():
    def __enter__(self):
        return time.time()

    def __exit__(self, type, value, traceback):
        pass


def is_float(s) -> bool:
    s = str(s)
    if s.count('.') == 1:
        left, right = s.split('.')  # [1,1]#-s.2
        if left.isdigit() and right.isdigit():
            return True
        elif left.startswith('-') and left.count('-') == 1 \
                and left[1:].isdigit() and right.isdigit():
            return True

    return False


def convert_value(value):
    if value.isdigit():
        return int(value)
    elif is_float(value):
        return float(value)
    elif value in {'True', 'False'}:
        return eval(value)
    else:
        return value


from ..loader.default_importer import model_lib
from ..loader.default_blend import blend_subpath_lib


class ConfigItemHelper():
    def __init__(self, item):
        self.item = item
        for key in item.__annotations__.keys():
            value = getattr(item, key)
            if key != 'prop_list':
                self.__setattr__(key, value)
            # prop list
            ops_config = dict()
            if len(item.prop_list) != 0:
                for prop_index, prop_item in enumerate(item.prop_list):
                    prop, value = prop_item.name, prop_item.value
                    # skip if the prop is not filled
                    if prop == '' or value == '': continue
                    ops_config[prop] = convert_value(value)
            self.__setattr__('prop_list', ops_config)

    def get_operator_and_args(self):
        op_callable = None
        ops_args = dict()
        operator_type = self.operator_type

        # custom operator
        if operator_type == 'CUSTOM':
            # custom operator
            bl_idname = self.bl_idname
            op_callable = getattr(getattr(bpy.ops, bl_idname.split('.')[0]), bl_idname.split('.')[1])
            ops_args = self.prop_list

        # default operator
        elif operator_type.startswith('DEFAULT'):
            bl_idname = model_lib.get(operator_type.removeprefix('DEFAULT_').lower())
            op_callable = getattr(getattr(bpy.ops, bl_idname.split('.')[0]), bl_idname.split('.')[1])

        elif operator_type.startswith('APPEND_BLEND'):
            subpath = operator_type.removeprefix('APPEND_BLEND_').title()
            data_type = blend_subpath_lib.get(subpath)
            op_callable = bpy.ops.wm.spio_append_blend
            ops_args = {'sub_path': subpath,
                        'data_type': data_type,
                        'load_all': True}

        elif operator_type.startswith('LINK_BLEND'):
            subpath = operator_type.removeprefix('LINK_BLEND_').title()
            data_type = blend_subpath_lib.get(subpath)
            op_callable = bpy.ops.wm.spio_link_blend
            ops_args = {'sub_path': subpath,
                        'data_type': data_type,
                        'load_all': True}

        return op_callable, ops_args

    def get_match_files(self, file_list):
        match_rule = self.match_rule
        match_value = self.match_value

        if match_rule == 'NONE':
            match_files = list()
        elif match_rule == 'STARTSWITH':
            match_files = [file for file in file_list if os.path.basename(file).startswith(match_value)]
        elif match_rule == 'ENDSWITH':
            match_files = [file for file in file_list if
                           os.path.basename(file).removesuffix('.' + self.ext).endswith(match_value)]
        elif match_rule == 'IN':
            match_files = [file for file in file_list if match_value in os.path.basename(file)]
        elif match_rule == 'REGEX':
            import re
            match_files = [file for file in file_list if re.search(match_value, os.path.basename(file))]

        return match_files


class ConfigHelper():
    def __init__(self, check_use=False, filter=None):
        pref_config = get_pref().config_list

        config_list = dict()
        index_list = []

        for config_list_index, item in enumerate(pref_config):
            # config dict
            config = dict()
            # get define property
            for key in item.__annotations__.keys():
                value = getattr(item, key)
                if key != 'prop_list':
                    config[key] = value
                # prop list
                ops_config = dict()
                if len(item.prop_list) != 0:
                    for prop_index, prop_item in enumerate(item.prop_list):
                        prop, value = prop_item.name, prop_item.value
                        # skip if the prop is not filled
                        if prop == '' or value == '': continue
                        ops_config[prop] = convert_value(value)
                config['prop_list'] = ops_config

            # check config dict
            if True in (config.get('name') == '',
                        config.get('operator_type') == 'CUSTOM' and config.get('bl_idname') == '',
                        config.get('extension') == '',
                        filter and config.get('extension') != filter,
                        check_use and config.get('use_config') is False,
                        ): continue

            index_list.append(config_list_index)
            config_list[item.name] = config

        self.config_list = config_list
        self.index_list = index_list

    def get_prop_list_from_index(self, index):
        if index > len(self.config_list) - 1: return None

        config_item = self.config_list[index]
        return config_item.get('prop_list')

    def is_empty(self):
        return len(self.config_list) == 0

    def is_only_one_config(self):
        return len(self.config_list) == 1

    def is_more_than_one_config(self):
        return len(self.config_list) > 1


class PopupMenu():
    def __init__(self, file_list, context):
        self.file_list = file_list
        self.context = context

    def default_image_menu(self, return_menu=False):
        context = self.context
        join_paths = '$$'.join(self.file_list)

        if context.area.type == "VIEW_3D":
            def draw_3dview_menu(cls, context):
                layout = cls.layout
                layout.operator_context = "INVOKE_DEFAULT"
                # only one blend need to deal with
                col = layout.column()
                op = col.operator('wm.spio_import_image', text=f'Import as reference')
                op.action = 'REF'
                op.files = join_paths

                op = col.operator('wm.spio_import_image', text=f'Import as Plane')
                op.action = 'PLANE'
                op.files = join_paths

            if return_menu:
                return draw_3dview_menu

            context.window_manager.popup_menu(draw_3dview_menu,
                                              title=f'Super Import Image ({len(self.file_list)} files)',
                                              icon='IMAGE_DATA')
        elif context.area.type == "NODE_EDITOR":
            bpy.ops.wm.spio_import_image(action='NODES', files=join_paths)

    def default_blend_menu(self, return_menu=False):
        context = self.context

        path = self.file_list[0]
        join_paths = '$$'.join(self.file_list)

        def draw_blend_menu(cls, context):
            pref = get_pref()
            layout = cls.layout
            layout.operator_context = "INVOKE_DEFAULT"
            # only one blend need to deal with
            if len(self.file_list) == 1:
                open = layout.operator('wm.spio_open_blend', icon='FILEBROWSER')
                open.filepath = path

                open = layout.operator('wm.spio_open_blend_extra', icon='ADD')
                open.filepath = path

                col = layout.column()

                col.separator()
                col.label(text = 'Append...',icon = 'APPEND_BLEND')
                for subpath, lib in blend_subpath_lib.items():
                    op = col.operator('wm.spio_append_blend', text=subpath)
                    op.filepath = path
                    op.sub_path = subpath
                    op.data_type = lib

                col.separator()
                col.label(text = 'Link...',icon = 'LINK_BLEND')
                for subpath, lib in blend_subpath_lib.items():
                    op = col.operator('wm.spio_link_blend', text=subpath)
                    op.filepath = path
                    op.sub_path = subpath
                    op.data_type = lib

            else:
                col = layout.column()
                op = col.operator('wm.spio_batch_import_blend', text=f'Batch Open')
                op.action = 'OPEN'
                op.files = join_paths

                for subpath, lib in blend_subpath_lib.items():
                    op = col.operator('wm.spio_batch_import_blend', text=f'Batch Append {subpath}')
                    op.action = 'APPEND'
                    op.files = join_paths
                    op.sub_path = subpath
                    op.data_type = lib

                col.separator()
                for subpath, lib in blend_subpath_lib.items():
                    op = col.operator('wm.spio_batch_import_blend', text=f'Batch Link {subpath}')
                    op.action = 'LINK'
                    op.files = join_paths
                    op.sub_path = subpath
                    op.data_type = lib

        # return for combine drawing
        if return_menu:
            return draw_blend_menu
        # popup
        context.window_manager.popup_menu(draw_blend_menu,
                                          title=f'Super Import Blend ({len(self.file_list)} files)',
                                          icon='FILE_BLEND')
