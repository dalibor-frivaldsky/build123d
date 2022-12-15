"""
Experimental Joint development file
"""
from __future__ import annotations
from math import inf
from abc import ABC, abstractmethod
from build123d import *


class Joint(ABC):
    """An object used to join two components together"""

    def __init__(self, parent: JointBox):
        self.parent: Solid = parent
        self.connected_to: Joint = None

    @abstractmethod
    def connect_to(self, other: Joint, **kwargs):
        """Connect Joint self by repositioning other"""
        return NotImplementedError

    @property
    @abstractmethod
    def symbol(self) -> Compound:
        """A CAD object positioned in global space to illustrate the joint"""
        return NotImplementedError


class RigidJoint(Joint):
    """A rigid joint fixes two components to one another"""

    @property
    def symbol(self) -> Compound:
        """A XYZ indicator object positioned in global space to illustrate the joint location"""
        size = self.parent.bounding_box().diagonal_length() / 12
        return SVG.axes(axes_scale=size).locate(
            self.parent.location * self.relative_location
        )

    def __init__(self, label: str, to_part: JointBox, joint_location: Location):
        self.relative_location = joint_location.relative_to(to_part.location)
        to_part.joints[label] = self
        super().__init__(to_part)

    def connect_to(self, other: RigidJoint):
        """Reposition parent of self relative to other"""
        other.parent.locate(
            self.parent.location * self.relative_location * other.relative_location
        )

        self.connected_to = other


class RevoluteJoint(Joint):
    """Component rotates around axis like a hinge"""

    @property
    def symbol(self) -> Compound:
        radius = self.parent.bounding_box().diagonal_length() / 30

        return Compound.make_compound(
            [
                Edge.make_line((0, 0, 0), (0, 0, radius * 10)),
                Edge.make_circle(radius),
            ]
        ).move(self.parent.location * self.relative_axis.to_location())

    def __init__(
        self,
        label: str,
        to_part: JointBox,
        axis: Axis,
        zero_rotation: VectorLike = None,
        range: tuple[float, float] = (0, 360),
    ):
        self.range = range
        if zero_rotation:
            if not axis.is_normal(Axis((0, 0, 0), self.zero_rotation)):
                raise ValueError("rotation_zero_direction must be normal to axis")
            self.zero_rotation = Vector(zero_rotation)
        else:
            self.zero_rotation = Plane(origin=(0, 0, 0), z_dir=axis.direction).x_dir
        self.angle = None
        self.relative_axis = axis.located(to_part.location.inverse())
        to_part.joints[label] = self
        super().__init__(to_part)

    def connect_to(self, other: RigidJoint, angle: float = None):
        """Reposition parent of self relative to other"""

        if not isinstance(other, RigidJoint):
            raise TypeError(f"other must of type RigidJoint not {type(other)}")

        angle = angle if angle else sum(self.range) / 2
        if not self.range[0] <= angle <= self.range[1]:
            raise ValueError(f"angle ({angle}) must in range of {self.range}")
        self.angle = angle
        rotation = Location(
            Plane(
                origin=(0, 0, 0),
                x_dir=self.zero_rotation.rotate(self.relative_axis, angle),
                z_dir=self.relative_axis.direction,
            )
        )
        new_location = (
            self.parent.location
            * self.relative_axis.to_location()
            * rotation
            * other.relative_location
        )
        other.parent.locate(new_location)
        self.connected_to = other


class LinearJoint(Joint):
    """Component moves along a single axis"""

    @property
    def symbol(self) -> Compound:
        """A CAD symbol of the linear axis positioned relative to_part"""
        radius = (self.range[1] - self.range[0]) / 15
        return Compound.make_compound(
            [
                Edge.make_line((0, 0, self.range[0]), (0, 0, self.range[1])),
                Edge.make_circle(radius),
            ]
        ).move(self.parent.location * self.relative_axis.to_location())

    def __init__(
        self,
        label: str,
        to_part: JointBox,
        axis: Axis,
        range: tuple[float, float] = (0, inf),
    ):
        self.axis = axis
        self.range = range
        self.position = None
        self.relative_axis = axis.located(to_part.location.inverse())
        to_part.joints[label]: dict[str, Joint] = self
        super().__init__(to_part)

    def connect_to(self, other: RigidJoint, position: float = None):
        """Reposition parent of other relative to linear joint defined by self"""

        if not isinstance(other, RigidJoint):
            raise TypeError(f"other must of type RigidJoint not {type(other)}")

        position = position if position is not None else sum(self.range) / 2
        if not self.range[0] <= position <= self.range[1]:
            raise ValueError(f"position ({position}) must in range of {self.range}")
        self.position = position
        joint_relative_location = Location(
            self.relative_axis.position + self.relative_axis.direction * position
        )
        other.parent.locate(self.parent.location * joint_relative_location)
        self.connected_to = other


class CylindricalJoint(Joint):
    """Component rotates around and moves along a single axis like a screw"""

    def __init__(
        self,
        rotational_axis: Axis,
        position_along_axis: float = None,
        rotational_range: tuple[float, float] = (0, 360),
        linear_range: tuple[float, float] = (0, inf),
    ):
        self.rotational_axis = rotational_axis
        self.position_along_axis = position_along_axis
        self.rotational_range = rotational_range
        self.linear_range = linear_range
        super().__init__(rotational_axis)


class PinSlotJoint(Joint):
    """Component rotates around one axis and moves along a different axis

    Slot is in slot_plane's positive X axis direction. Pin rotates about an Axis parallel to
    slot_plane's Z axis.
    """

    def __init__(
        self,
        slot_plane: Plane,
        pin_rotation: float = None,
        pin_position: float = None,
        rotational_range: tuple[float, float] = (0, 360),
        linear_range: tuple[float, float] = (0, inf),
    ):
        self.slot_plane = slot_plane
        self.pin_rotation = pin_rotation
        self.pin_position = pin_position
        self.rotational_range = rotational_range
        self.linear_axis = slot_plane
        self.linear_range = linear_range
        super().__init__(slot_plane)


class PlanarJoint(Joint):
    """Component moves along two axes and rotates around a single axis"""

    def __init__(
        self,
        plane: Plane,
        rotational_origin: tuple[float, float],
        planar_range: tuple[tuple[float, float], tuple[float, float]] = (
            (-inf, inf),
            (-inf, inf),
        ),
        rotational_range: tuple[float, float] = None,
    ):
        self.plane = plane
        self.rotational_origin = rotational_origin
        self.planar_range = planar_range
        self.rotational_range = rotational_range
        super().__init__(plane)


class BallJoint(Joint):
    """Component rotates around all 3 axes using a gimbal system (3 nested rotations)"""

    def __init__(
        self,
        joint_position: VectorLike,
        joint_rotation: tuple[float, float, float] = None,
        rotational_range: tuple[
            tuple[float, float], tuple[float, float], tuple[float, float]
        ] = ((0, 360), (0, 360), (0, 360)),
    ):
        self.joint_position = joint_position
        self.joint_rotation = joint_rotation
        self.rotational_range = rotational_range
        super().__init__(Location(Vector(joint_position)))


class JointBox(Solid):
    """A filleted box with joints

    A box of the given dimensions with all of the edges filleted.

    Args:
        length (float): box length
        width (float): box width
        height (float): box height
        radius (float): edge radius
    """

    def __init__(
        self,
        length: float,
        width: float,
        height: float,
        radius: float = 0.0,
    ):
        # Store the attributes so the object can be copied
        self.length = length
        self.width = width
        self.height = height
        self.joints: dict[str, Joint] = {}

        # Create the object
        obj = Solid.make_box(length, width, height, Plane((-length / 2, -width / 2, 0)))
        if radius != 0.0:
            obj = obj.fillet(radius, obj.edges())
        hole = Solid.make_cylinder(width / 4, length, Plane.YZ.offset(-length / 2))
        obj = obj.cut(hole)
        # Initialize the Solid class with the new OCCT object
        super().__init__(obj.wrapped)


#
# Base Object
#
# base = JointBox(10, 10, 10)
# base = JointBox(10, 10, 10).locate(Location(Vector(1, 1, 1)))
# base = JointBox(10, 10, 10).locate(Location(Vector(1, 1, 1), (1, 0, 0), 5))
base = JointBox(10, 10, 10).locate(Location(Vector(1, 1, 1), (1, 1, 1), 30))

#
# Rigid Joint
#
fixed_arm = JointBox(1, 1, 5, 0.2)
j1 = RigidJoint("side", base, Plane(base.faces().sort_by(Axis.X)[-1]).to_location())
j2 = RigidJoint(
    "top", fixed_arm, (-Plane(fixed_arm.faces().sort_by(Axis.Z)[-1])).to_location()
)
base.joints["side"].connect_to(fixed_arm.joints["top"])
# or
# j1.connect_to(j2)

#
# Hinge
#
hinge_arm = JointBox(2, 1, 10)
swing_arm_hinge_edge: Edge = hinge_arm.edges().sort_by(Axis((0, 0, 0), (-1, 0.5, 0)))[
    -1
]
swing_arm_hinge_axis = (
    hinge_arm.edges().sort_by(Axis((0, 0, 0), (-1, 0.5, 0)))[-1].to_axis()
)
base_corner_edge = base.edges().sort_by(Axis((0, 0, 0), (1, 1, 0)))[-1]
base_hinge_axis = base_corner_edge.to_axis()
j3 = RevoluteJoint("hinge", base, axis=base_hinge_axis, range=(0, 360))
j4 = RigidJoint("corner", hinge_arm, swing_arm_hinge_axis.to_location())
base.joints["hinge"].connect_to(hinge_arm.joints["corner"], angle=180)

#
# Slider
#
slider_arm = JointBox(4, 1, 2, 0.2)
top_face_corners = ShapeList(
    [v.to_vector() for v in base.faces().sort_by(Axis.Z)[-1].vertices()]
)
slide_ends = [
    (top_face_corners.sort_by(Axis.X)[0] + top_face_corners.sort_by(Axis.X)[1]) * 0.5,
    (top_face_corners.sort_by(Axis.X)[-2] + top_face_corners.sort_by(Axis.X)[-1]) * 0.5,
]
slide_axis = Axis(slide_ends[0], slide_ends[1] - slide_ends[0])
s1 = LinearJoint("slide", base, axis=slide_axis, range=(0, 10))
s2 = RigidJoint("slide", slider_arm, Location(Vector(0, 0, 0)))
base.joints["slide"].connect_to(slider_arm.joints["slide"], position=8)


if "show_object" in locals():
    show_object(base, name="base", options={"alpha": 0.8})
    show_object(base.joints["side"].symbol, name="side joint")
    show_object(base.joints["hinge"].symbol, name="hinge joint")
    show_object(base.joints["slide"].symbol, name="slot joint")
    show_object(fixed_arm, name="fixed_arm", options={"alpha": 0.6})
    show_object(hinge_arm, name="hinge_arm", options={"alpha": 0.6})
    show_object(slider_arm, name="slider_arm", options={"alpha": 0.6})
    show_object(slider_arm.joints["slide"].symbol, name="slider attachment")
