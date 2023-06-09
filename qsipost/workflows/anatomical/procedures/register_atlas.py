from nipype.interfaces import utility as niu
from nipype.interfaces.ants import ApplyTransforms
from nipype.pipeline import engine as pe


def init_registration_wf(
    name: str = "atlas_registration",
):
    """
    Initialize the registration workflow.

    Parameters
    ----------
    name : str, optional
        The name of the workflow, by default "registration"
    """
    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(
        interface=niu.IdentityInterface(
            fields=[
                "anatomical_reference",
                "mni_to_native_transform",
                "atlas_name",
                "atlas_nifti_file",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        interface=niu.IdentityInterface(
            fields=[
                "whole_brain_parcellation",
            ]
        ),
        name="outputnode",
    )
    apply_transforms = pe.Node(
        interface=ApplyTransforms(
            interpolation="NearestNeighbor",
        ),
        name="apply_transforms",
    )
    workflow.connect(
        [
            (
                inputnode,
                apply_transforms,
                [
                    ("atlas_nifti_file", "input_image"),
                    ("mni_to_native_transform", "transforms"),
                    ("anatomical_reference", "reference_image"),
                ],
            ),
            (
                apply_transforms,
                outputnode,
                [
                    ("output_image", "whole_brain_parcellation"),
                ],
            ),
        ]
    )
    return workflow
