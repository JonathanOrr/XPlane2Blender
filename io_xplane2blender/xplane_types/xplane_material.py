
import bpy

from io_xplane2blender.xplane_types import xplane_object

from ..xplane_config import getDebug
from ..xplane_constants import *
from ..xplane_helpers import (
    effective_normal_metalness,
    unfinished,
)
from .xplane_attribute import XPlaneAttribute
from .xplane_attributes import XPlaneAttributes


# Class: XPlaneMaterial
# A Material
class XPlaneMaterial:
    # Property: object
    # XPlaneObject - A <XPlaneObject>

    # Property: texture
    # string - Path to the texture in use for this material, or None if no texture is present.
    # This property is no longer important as textures are defined by layer.

    # Property: uv_name
    # string - Name of the uv layer to be used for texture UVs.

    # Property: name
    # string - Name of the Blender material.

    # Property: attributes
    # dict - Material attributes that will be turned into commands with <XPlaneCommands>.

    # Constructor: __init__
    # Defines the <attributes> by reading the original Blender material from the <object>.
    # Also adds custom attributes to <attributes>.
    #
    # Parameters:
    #   xplaneObject - A <XPlaneObject>
    def __init__(self, xplaneObject: xplane_object.XPlaneObject):

        self.xplaneObject = xplaneObject
        self.blenderObject = self.xplaneObject.blenderObject
        self.blenderMaterial = None
        # The options from mat.xplane
        self.options = None
        self.texture = None
        self.textureLit = None
        self.textureNormal = None
        self.textureSpecular = None
        self.uv_name = None
        self.name = None

        # Material
        self.attributes = XPlaneAttributes()

        self.attributes.add(XPlaneAttribute("ATTR_shiny_rat"))
        self.attributes.add(XPlaneAttribute("ATTR_hard"))
        self.attributes.add(XPlaneAttribute("ATTR_hard_deck"))
        self.attributes.add(XPlaneAttribute("ATTR_no_hard"))

        self.attributes.add(XPlaneAttribute("ATTR_blend"))
        self.attributes.add(XPlaneAttribute("ATTR_shadow_blend"))
        self.attributes.add(XPlaneAttribute("ATTR_no_blend"))

        self.attributes.add(XPlaneAttribute("ATTR_shadow"))
        self.attributes.add(XPlaneAttribute("ATTR_no_shadow"))
        self.attributes.add(XPlaneAttribute("ATTR_draw_enable"))
        self.attributes.add(XPlaneAttribute("ATTR_draw_disable"))
        self.attributes.add(XPlaneAttribute("ATTR_solid_camera"))
        self.attributes.add(XPlaneAttribute("ATTR_no_solid_camera"))

        # These weights are hueristics
        self.attributes.add(XPlaneAttribute("ATTR_light_level", None, 1000))
        self.attributes.add(XPlaneAttribute("ATTR_light_level_reset", True, 1000))
        self.attributes.add(XPlaneAttribute("ATTR_poly_os", None, 1000))

        self.cockpitAttributes = XPlaneAttributes()
        self.cockpitAttributes.add(XPlaneAttribute("ATTR_cockpit_device", None, 2000))
        self.cockpitAttributes.add(XPlaneAttribute("ATTR_cockpit", None, 2000))
        self.cockpitAttributes.add(XPlaneAttribute("ATTR_cockpit_lit_only", None, 2000))
        self.cockpitAttributes.add(XPlaneAttribute("ATTR_cockpit_hud", None, 2000))
        self.cockpitAttributes.add(XPlaneAttribute("ATTR_cockpit_region", None, 2000))
        self.cockpitAttributes.add(XPlaneAttribute("ATTR_no_cockpit", True, 2000))

    def collect(self) -> None:
        if (
            self.blenderObject.material_slots
            and self.blenderObject.material_slots[0].material
        ):
            mat = self.blenderObject.material_slots[0].material
            self.name = mat.name
            self.blenderMaterial = mat
            self.options = mat.xplane  # type: xplane_props.XPlaneMaterialSettings

            if mat.xplane.draw:
                self.attributes["ATTR_draw_enable"].setValue(True)

                # add cockpit attributes
                self.collectCockpitAttributes(mat)

                # add light level attritubes
                self.collectLightLevelAttributes(mat)

                # polygon offsett attribute
                if mat.xplane.poly_os > 0:
                    self.attributes["ATTR_poly_os"].setValue(mat.xplane.poly_os)

                if mat.xplane.cockpit_feature == COCKPIT_FEATURE_NONE:
                    if not effective_normal_metalness(self.xplaneObject.xplaneBone.xplaneFile):
                        self.attributes["ATTR_shiny_rat"].setValue(mat.specular_intensity)

                    blend = mat.xplane.blend_v1000
                    if blend == BLEND_OFF:
                        self.attributes["ATTR_no_blend"].setValue(mat.xplane.blendRatio)
                    elif blend == BLEND_ON:
                        self.attributes["ATTR_blend"].setValue(True)
                    elif blend == BLEND_SHADOW:
                        self.attributes["ATTR_shadow_blend"].setValue(mat.xplane.blendRatio)

                    self.attributes["ATTR_shadow"].setValue(mat.xplane.shadow_local)
                    self.attributes["ATTR_no_shadow"].setValue(not mat.xplane.shadow_local)
            else:
                self.attributes["ATTR_draw_disable"].setValue(True)

            # surface type
            if mat.xplane.surfaceType != SURFACE_TYPE_NONE:
                if mat.xplane.deck:
                    self.attributes["ATTR_hard_deck"].setValue(mat.xplane.surfaceType)
                else:
                    self.attributes["ATTR_hard"].setValue(mat.xplane.surfaceType)
            else:
                self.attributes["ATTR_no_hard"].setValue(True)

            # camera collision
            if mat.xplane.solid_camera:
                self.attributes["ATTR_solid_camera"].setValue(True)
                self.attributes["ATTR_no_solid_camera"].setValue(False)
            else:
                self.attributes["ATTR_no_solid_camera"].setValue(True)

            # try to find uv layer
            if len(self.blenderObject.data.uv_layers) > 0:
                self.uv_name = self.blenderObject.data.uv_layers.active.name

            # add custom attributes
            self.collectCustomAttributes(mat)

        else:
            # A part that has no material yet still exports, with X-Plane's default material state
            unfinished.add(
                "meshes without a material (default material used)",
                self.blenderObject.name,
            )

        self.attributes.order()

    def collectCustomAttributes(self, mat: bpy.types.Material) -> None:
        xplaneFile = self.xplaneObject.xplaneBone.xplaneFile
        commands = xplaneFile.commands

        if mat.xplane.customAttributes:
            for attr in mat.xplane.customAttributes:
                if attr.reset:
                    commands.addReseter(attr.name, attr.reset)
                self.attributes.add(XPlaneAttribute(attr.name, attr.value, attr.weight))

    def collectCockpitAttributes(self, mat: bpy.types.Material) -> None:
        xplaneFile = self.xplaneObject.xplaneBone.xplaneFile
        # cockpit_panel_feature is what Cockpit Feature is getting used, found in the Material settings
        # cockpit_panel_mode is how 'Cockpit Feature: Panel Texture' is treated, found in the OBJ settings
        # Cockpit Feature relies on Panel Modes, not the other way around
        #
        # Table:
        # Panel Mode | Valid Cockpit Feature
        # -----------|----------------------
        # Default    |  None, Panel, (Regions == 0), Device
        # Emissive   |  None, Panel, (Regions == 0), Device?
        # Regions    |  None?, Panel?, (Regions > 0), Device?
        #
        # TODO ? means "Ben must clarify what should happen here".
        # Currently any invalid case is just ignored.
        #
        # The cockpit_panel_mode enum was weirdly composed thanks to the header prop like-nature of
        # ATTR_cockpit_lit_only and a convenient way to make Regions only show up as needed.
        # It makes the cockpit panel feature harder to understand sadly. -Ted 1/22/2021
        # --- Cockpit Panel Mode/Feature --------------------------------------
        cockpit_panel_mode = xplaneFile.options.cockpit_panel_mode
        cockpit_panel_feature = mat.xplane.cockpit_feature
        if mat.xplane.cockpit_feature != COCKPIT_FEATURE_NONE:
            self.cockpitAttributes["ATTR_no_cockpit"].setValue(None)

        if mat.xplane.cockpit_feature == COCKPIT_FEATURE_DEVICE:
            device = mat.xplane.plugin_device if mat.xplane.device_name == DEVICE_PLUGIN else mat.xplane.device_name
            value = [
                device,
                sum(getattr(mat.xplane, f"device_bus_{i}") << i for i in range(6)),
                mat.xplane.device_lighting_channel,
                mat.xplane.device_auto_adjust,
            ]
            if mat.xplane.cockpit_feature_use_luminance:
                value.append(mat.xplane.cockpit_feature_luminance)
            self.cockpitAttributes["ATTR_cockpit_device"].value[0] = value

        elif cockpit_panel_feature == COCKPIT_FEATURE_PANEL:
            cockpit_region = int(mat.xplane.cockpit_region)
            # fmt: off
            ckpt_attrs = self.cockpitAttributes
            attr = {
                PANEL_COCKPIT:          ckpt_attrs["ATTR_cockpit"],
                PANEL_COCKPIT_LIT_ONLY: ckpt_attrs["ATTR_cockpit_lit_only"],
                PANEL_COCKPIT_REGION:   ckpt_attrs["ATTR_cockpit_region"],
            }[cockpit_panel_mode]
            # fmt: on
            value = []
            if cockpit_panel_mode == PANEL_COCKPIT_REGION and cockpit_region:
                value.append(cockpit_region - 1)
            if mat.xplane.cockpit_feature_use_luminance:
                value.append(mat.xplane.cockpit_feature_luminance)

            if value:
                attr.value[0] = value
            else:
                attr.value = [True]
        # ---------------------------------------------------------------------

    def collectLightLevelAttributes(self, mat: bpy.types.Material) -> None:
        if (
            mat.xplane.lightLevel
            and not self.xplaneObject.blenderObject.xplane.lightLevel
            and not mat.xplane.lightLevel_dataref.strip()
        ):
            # Not filled in yet. Without a dataref the line would be invalid, so leave it out
            unfinished.add("light levels without a dataref", f"material {mat.name}")
        elif (
            mat.xplane.lightLevel
            and not self.xplaneObject.blenderObject.xplane.lightLevel
        ):
            ll_values = [
                mat.xplane.lightLevel_v1,
                mat.xplane.lightLevel_v2,
                mat.xplane.lightLevel_dataref,
            ]
            if mat.xplane.lightLevel_photometric:
                ll_values.append(mat.xplane.lightLevel_brightness)
            self.attributes["ATTR_light_level"].setValue(tuple(ll_values))
            self.attributes["ATTR_light_level_reset"].setValue(False)
        elif not self.xplaneObject.blenderObject.xplane.lightLevel:
            # A custom light level on a parent mesh covers its descendants.
            # Default material state must not erase it before their triangles.
            bone = self.xplaneObject.xplaneBone
            while bone:
                obj = bone.xplaneObject
                if obj and not obj.export_animation_only:
                    reset = obj.attributes.get("ATTR_light_level_reset")
                    if reset and any(
                        value is not None and value is not False
                        for value in reset.getValues()
                    ):
                        break
                    attr = obj.attributes.get("ATTR_light_level")
                    if (
                        not obj.blenderObject.xplane.lightLevel
                        and attr
                        and any(value is not None for value in attr.getValues())
                    ):
                        if obj is not self.xplaneObject:
                            self.attributes["ATTR_light_level"].value = (
                                attr.value.copy()
                            )
                        self.attributes["ATTR_light_level_reset"].setValue(False)
                        break
                bone = bone.parent

    def write(self) -> str:
        debug = getDebug()
        o = ""
        indent = self.xplaneObject.xplaneBone.getIndent()

        if debug:
            o += indent + "# MATERIAL: %s\n" % (self.name)

        xplaneFile = self.xplaneObject.xplaneBone.xplaneFile
        commands = xplaneFile.commands

        for attr in self.attributes:
            o += commands.writeAttribute(self.attributes[attr], self.xplaneObject)

        for attr in self.cockpitAttributes:
            o += commands.writeAttribute(self.cockpitAttributes[attr], self.xplaneObject)

        return o
