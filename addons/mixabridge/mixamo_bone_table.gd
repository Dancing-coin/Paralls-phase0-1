@tool
class_name MixamoBoneTable
extends RefCounted

const MIXAMO_PREFIX_COLON := "mixamorig:"
const MIXAMO_PREFIX_UNDERSCORE := "mixamorig_"

const BONE_MAP: Dictionary = {
	"Hips": "Hips",
	"Spine": "Spine",
	"Spine1": "Chest",
	"Spine2": "UpperChest",
	"Neck": "Neck",
	"Head": "Head",
	"HeadTop_End": "",

	"LeftShoulder": "LeftShoulder",
	"LeftArm": "LeftUpperArm",
	"LeftForeArm": "LeftLowerArm",
	"LeftHand": "LeftHand",

	"RightShoulder": "RightShoulder",
	"RightArm": "RightUpperArm",
	"RightForeArm": "RightLowerArm",
	"RightHand": "RightHand",

	"LeftUpLeg": "LeftUpperLeg",
	"LeftLeg": "LeftLowerLeg",
	"LeftFoot": "LeftFoot",
	"LeftToeBase": "LeftToes",
	"LeftToe_End": "",

	"RightUpLeg": "RightUpperLeg",
	"RightLeg": "RightLowerLeg",
	"RightFoot": "RightFoot",
	"RightToeBase": "RightToes",
	"RightToe_End": "",

	"LeftHandThumb1": "LeftThumbMetacarpal",
	"LeftHandThumb2": "LeftThumbProximal",
	"LeftHandThumb3": "LeftThumbDistal",
	"LeftHandThumb4": "",
	"LeftHandIndex1": "LeftIndexProximal",
	"LeftHandIndex2": "LeftIndexIntermediate",
	"LeftHandIndex3": "LeftIndexDistal",
	"LeftHandIndex4": "",
	"LeftHandMiddle1": "LeftMiddleProximal",
	"LeftHandMiddle2": "LeftMiddleIntermediate",
	"LeftHandMiddle3": "LeftMiddleDistal",
	"LeftHandMiddle4": "",
	"LeftHandRing1": "LeftRingProximal",
	"LeftHandRing2": "LeftRingIntermediate",
	"LeftHandRing3": "LeftRingDistal",
	"LeftHandRing4": "",
	"LeftHandPinky1": "LeftLittleProximal",
	"LeftHandPinky2": "LeftLittleIntermediate",
	"LeftHandPinky3": "LeftLittleDistal",
	"LeftHandPinky4": "",

	"RightHandThumb1": "RightThumbMetacarpal",
	"RightHandThumb2": "RightThumbProximal",
	"RightHandThumb3": "RightThumbDistal",
	"RightHandThumb4": "",
	"RightHandIndex1": "RightIndexProximal",
	"RightHandIndex2": "RightIndexIntermediate",
	"RightHandIndex3": "RightIndexDistal",
	"RightHandIndex4": "",
	"RightHandMiddle1": "RightMiddleProximal",
	"RightHandMiddle2": "RightMiddleIntermediate",
	"RightHandMiddle3": "RightMiddleDistal",
	"RightHandMiddle4": "",
	"RightHandRing1": "RightRingProximal",
	"RightHandRing2": "RightRingIntermediate",
	"RightHandRing3": "RightRingDistal",
	"RightHandRing4": "",
	"RightHandPinky1": "RightLittleProximal",
	"RightHandPinky2": "RightLittleIntermediate",
	"RightHandPinky3": "RightLittleDistal",
	"RightHandPinky4": "",

	# GodotPlush / DEF-style local rig compatibility.
	"DEF-hips": "Hips",
	"DEF-upper_arm.L": "LeftUpperArm",
	"DEF-forearm.L": "LeftLowerArm",
	"DEF-upper_arm.R": "RightUpperArm",
	"DEF-forearm.R": "RightLowerArm",
	"DEF-thigh.L": "LeftUpperLeg",
	"DEF-shin.L": "LeftLowerLeg",
	"DEF-foot.L": "LeftFoot",
	"DEF-thigh.R": "RightUpperLeg",
	"DEF-shin.R": "RightLowerLeg",
	"DEF-foot.R": "RightFoot",

	# 3ds Max Biped compatibility for the crusader knight rig.
	"Bip001 Pelvis": "Hips",
	"Bip001 Spine": "Spine",
	"Bip001 Spine1": "Chest",
	"Bip001 Spine2": "UpperChest",
	"Bip001 Neck": "Neck",
	"Bip001 Head": "Head",
	"Bip001 L Clavicle": "LeftShoulder",
	"Bip001 L UpperArm": "LeftUpperArm",
	"Bip001 L Forearm": "LeftLowerArm",
	"Bip001 L Hand": "LeftHand",
	"Bip001 R Clavicle": "RightShoulder",
	"Bip001 R UpperArm": "RightUpperArm",
	"Bip001 R Forearm": "RightLowerArm",
	"Bip001 R Hand": "RightHand",
	"Bip001 L Thigh": "LeftUpperLeg",
	"Bip001 L Calf": "LeftLowerLeg",
	"Bip001 L Foot": "LeftFoot",
	"Bip001 L Toe0": "LeftToes",
	"Bip001 R Thigh": "RightUpperLeg",
	"Bip001 R Calf": "RightLowerLeg",
	"Bip001 R Foot": "RightFoot",
	"Bip001 R Toe0": "RightToes",
	"Bip001 L Finger0": "LeftThumbMetacarpal",
	"Bip001 L Finger01": "LeftThumbProximal",
	"Bip001 L Finger02": "LeftThumbDistal",
	"Bip001 L Finger1": "LeftIndexProximal",
	"Bip001 L Finger11": "LeftIndexIntermediate",
	"Bip001 L Finger12": "LeftIndexDistal",
	"Bip001 L Finger2": "LeftMiddleProximal",
	"Bip001 L Finger21": "LeftMiddleIntermediate",
	"Bip001 L Finger22": "LeftMiddleDistal",
	"Bip001 L Finger3": "LeftRingProximal",
	"Bip001 L Finger31": "LeftRingIntermediate",
	"Bip001 L Finger32": "LeftRingDistal",
	"Bip001 L Finger4": "LeftLittleProximal",
	"Bip001 L Finger41": "LeftLittleIntermediate",
	"Bip001 L Finger42": "LeftLittleDistal",
	"Bip001 R Finger0": "RightThumbMetacarpal",
	"Bip001 R Finger01": "RightThumbProximal",
	"Bip001 R Finger02": "RightThumbDistal",
	"Bip001 R Finger1": "RightIndexProximal",
	"Bip001 R Finger11": "RightIndexIntermediate",
	"Bip001 R Finger12": "RightIndexDistal",
	"Bip001 R Finger2": "RightMiddleProximal",
	"Bip001 R Finger21": "RightMiddleIntermediate",
	"Bip001 R Finger22": "RightMiddleDistal",
	"Bip001 R Finger3": "RightRingProximal",
	"Bip001 R Finger31": "RightRingIntermediate",
	"Bip001 R Finger32": "RightRingDistal",
	"Bip001 R Finger4": "RightLittleProximal",
	"Bip001 R Finger41": "RightLittleIntermediate",
	"Bip001 R Finger42": "RightLittleDistal",
}


static func strip_mixamo_prefix(bone_name: String) -> String:
	if bone_name.begins_with(MIXAMO_PREFIX_COLON):
		return bone_name.substr(MIXAMO_PREFIX_COLON.length())
	if bone_name.begins_with(MIXAMO_PREFIX_UNDERSCORE):
		return bone_name.substr(MIXAMO_PREFIX_UNDERSCORE.length())
	return bone_name


static func get_profile_bone_name(mixamo_name: String) -> String:
	var stripped := strip_mixamo_prefix(mixamo_name)
	if BONE_MAP.has(stripped):
		return BONE_MAP[stripped]
	return ""


static func detect_mixamo_prefix(skeleton: Skeleton3D) -> String:
	for bone_idx: int in skeleton.get_bone_count():
		var bone_name: String = skeleton.get_bone_name(bone_idx)
		if bone_name.begins_with(MIXAMO_PREFIX_COLON):
			return MIXAMO_PREFIX_COLON
		if bone_name.begins_with(MIXAMO_PREFIX_UNDERSCORE):
			return MIXAMO_PREFIX_UNDERSCORE
	return ""
