from nipype.interfaces import mrtrix3
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe

from qsipost import config
from qsipost.interfaces.bids import DerivativesDataSink
from qsipost.workflows.diffusion.procedures.utils.derivatives import (
    DIFFUSION_WF_OUTPUT_ENTITIES,
)

TENSOR_PARAMETERS = [
    "adc",
    "fa",
    "ad",
    "rd",
    "cl",
    "cp",
    "cs",
    "evec",
    "eval",
]


def init_mrtrix3_tensor_wf(name: str = "mrtrix3_tensor_wf") -> pe.Workflow:
    """
    Initialize the tensor estimation workflow.

    Parameters
    ----------
    name : str, optional
            The name of the workflow, by default "tensor_estimation_wf"

    Returns
    -------
    pe.Workflow
            The tensor estimation workflow
    """
    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(
        interface=niu.IdentityInterface(
            fields=[
                "base_directory",
                "dwi_nifti",
                "dwi_grad",
                "dwi_mask",
            ]
        ),
        name="inputnode",
    )
    outputnode = pe.Node(
        interface=niu.IdentityInterface(fields=TENSOR_PARAMETERS),
        name="outputnode",
    )
    dwi2tensor_wf = pe.Node(
        interface=mrtrix3.FitTensor(nthreads=config.nipype.omp_nthreads),
        name="mrtrix3_tensor_wf",
    )
    tensor2metric_wf = pe.Node(
        interface=mrtrix3.TensorMetrics(
            **{f"out_{param}": f"{param}.nii.gz" for param in TENSOR_PARAMETERS},
        ),
        name="mrtrix3_tensor2metric_wf",
    )
    listify_metrics_wf = pe.Node(
        interface=niu.Merge(len(TENSOR_PARAMETERS)),
        name="listify_tensor_params",
    )
    ds_tensor_wf = pe.MapNode(
        interface=DerivativesDataSink(
            **DIFFUSION_WF_OUTPUT_ENTITIES.get("dti_derived_parameters"),
            reconstruction_software="mrtrix3",
            save_meta=False,
        ),
        iterfield=["in_file", "desc"],
        name="ds_tensor_wf",
    )
    ds_tensor_wf.inputs.desc = TENSOR_PARAMETERS

    workflow.connect(
        [
            (
                inputnode,
                dwi2tensor_wf,
                [
                    ("dwi_nifti", "in_file"),
                    ("dwi_grad", "grad_file"),
                    ("dwi_mask", "in_mask"),
                ],
            ),
            (
                dwi2tensor_wf,
                tensor2metric_wf,
                [
                    ("out_file", "in_file"),
                ],
            ),
            (
                tensor2metric_wf,
                outputnode,
                [(f"out_{param}", param) for param in TENSOR_PARAMETERS],
            ),
            (
                outputnode,
                listify_metrics_wf,
                [(param, f"in{i+1}") for i, param in enumerate(TENSOR_PARAMETERS)],
            ),
            (
                listify_metrics_wf,
                ds_tensor_wf,
                [("out", "in_file")],
            ),
            (
                inputnode,
                ds_tensor_wf,
                [
                    ("base_directory", "base_directory"),
                    ("dwi_nifti", "source_file"),
                ],
            ),
        ]
    )
    return workflow
