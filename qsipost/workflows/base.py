from typing import Union

from copy import deepcopy
from pathlib import Path

from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from packaging.version import Version

from qsipost import config
from qsipost.bids.layout import QSIPREPLayout
from qsipost.parcellations.atlases.atlas import Atlas
from qsipost.workflows.anatomical.anatomical import init_anatomical_wf
from qsipost.workflows.diffusion.diffusion import init_diffusion_wf
from qsipost.workflows.utils.bids import collect_data


def init_qsipost_wf(
    # layout: QSIPREPLayout,
    # output_dir: Union[str, Path] = None,
    # subjects_list: list = [],
    # parcellation_atlas: Union[str, Atlas] = "brainnetome",
    # work_dir: Union[str, Path] = None,
    # stop_on_first_crash: bool = False,
    # write_graph: bool = True,
):
    """
    Initialize the qsipost workflow.

    Parameters
    ----------
    layout : QSIPREPLayout
        The BIDSLayout object.
    subjects_list : list, optional
        List of subjects to be processed. The default is [].
    work_dir : Union[str, Path], optional
        The working directory. The default is None.
    """
    parcellation_atlas = config.workflow.parcellation_atlas
    if isinstance(parcellation_atlas, str):
        parcellation_atlas = Atlas(parcellation_atlas, load_existing=True)
        if not hasattr(parcellation_atlas, "atlas_nifti_file"):
            raise ValueError(
                f"Could not find the atlas {parcellation_atlas.name} in the "
                "configured atlas directory. Please check the name or initialize "
                "a corresponding Atlas object."
            )

    ver = Version(config.environment.version)
    qsipost_wf = pe.Workflow(name=f"qsipost_{ver.major}_{ver.minor}_wf")
    qsipost_wf.base_dir = config.execution.work_dir
    # qsipost_wf.base_dir = str(work_dir.resolve())
    for subject_id in config.execution.participant_label:
        name = f"single_subject_{subject_id}_wf"
        # try:
        single_subject_wf = init_single_subject_wf(
            subject_id=subject_id,
            parcellation_atlas=parcellation_atlas,
        )
        single_subject_wf.config["execution"]["crashdump_dir"] = str(
            config.execution.output_dir
            / f"sub-{subject_id}"
            / "log"
            / config.execution.run_uuid
        )
        # single_subject_wf.config["execution"]["crashdump_dir"] = str(
        #     Path(layout.root) / f"sub-{subject_id}/log"
        # )
        for node in single_subject_wf._get_all_nodes():
            node.config = deepcopy(single_subject_wf.config)
        # single_subject_wf.base_dir = str(work_dir.resolve())
        qsipost_wf.add_nodes([single_subject_wf])
        if config.execution.write_graph:
            wf_to_write = qsipost_wf.get_node(name)
            wf_to_write.base_dir = str(qsipost_wf.base_dir / qsipost_wf.name)
            wf_to_write.write_graph(graph2use="colored", format="svg", simple_form=True)
        log_dir = (
            config.execution.output_dir
            / f"sub-{subject_id}"
            / "log"
            / config.execution.run_uuid
        )
        log_dir.mkdir(exist_ok=True, parents=True)
        config.to_filename(log_dir / "qsipost.toml")
        # except Exception as e:
        #     if stop_on_first_crash:
        #         raise e
        #     else:
        #         print(
        #             f"Could not process subject {subject_id}. "
        #             f"Error: {e}. Skipping..."
        #         )
    return qsipost_wf


def init_single_subject_wf(
    # layout: QSIPREPLayout,
    subject_id: str,
    parcellation_atlas: Atlas,
    # output_dir: Union[str, Path] = None,
    # name: str = None,
    # work_dir: Union[str, Path] = None,
):
    """
    Initialize the qsipost workflow for a single subject.

    Parameters
    ----------
    layout : QSIPREPLayout
        The BIDSLayout object.
    subject_id : str
        The subject ID.
    """
    # work_dir = Path(work_dir or "qsipost_wf")
    # work_dir.mkdir(exist_ok=True, parents=True)

    # output_dir = (
    #     Path(output_dir)
    #     if output_dir is not None
    #     else Path(layout.root).parent / "qsipost"
    # )
    # output_dir.mkdir(exist_ok=True, parents=True)
    # workflow.base_dir = str(work_dir.resolve())
    qsiprep_ver = config.execution.layout.description["PipelineDescription"]["Version"]
    name = f"single_subject_{subject_id}_wf"
    workflow = pe.Workflow(name=name)
    workflow.__desc__ = f"""
    The qsipost workflow performs post-processing of diffusion MRI data.
    It relies on the outputs of *QSIprep* {qsiprep_ver} (@qsiprep), and
    is based on *Nipype* {config.environment.nipype_version} (@nipype1; @nipype2; RRID:SCR_002502).
    """

    qsipost_dir = config.execution.output_dir
    freesurfer_dir = Path(qsipost_dir).parent / "freesurfer"
    freesurfer_dir.mkdir(exist_ok=True, parents=True)
    anat_only = config.workflow.anat_only

    subject_data, sessions_data = collect_data(
        layout=config.execution.layout, participant_label=subject_id
    )

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "base_directory",
                "anatomical_reference",
                "anatomical_brain_mask",
                "mni_to_native_transform",
                "gm_probabilistic_segmentation",
                "atlas_name",
                "atlas_nifti",
                "atlas_table",
                "label_column",
                "subject_id",
                "freesurfer_dir",
            ]
        ),
        name="inputnode_subject",
    )
    inputnode.inputs.base_directory = qsipost_dir
    inputnode.inputs.atlas_name = parcellation_atlas.name
    inputnode.inputs.atlas_nifti_file = parcellation_atlas.atlas_nifti_file
    inputnode.inputs.atlas_table = parcellation_atlas.description_csv
    inputnode.inputs.label_column = parcellation_atlas.label_name
    inputnode.inputs.anatomical_reference = subject_data["anatomical_reference"]
    inputnode.inputs.anatomical_brain_mask = subject_data["anatomical_brain_mask"]
    inputnode.inputs.mni_to_native_transform = subject_data["mni_to_native_transform"]
    inputnode.inputs.gm_probabilistic_segmentation = subject_data[
        "gm_probabilistic_segmentation"
    ]
    inputnode.inputs.subject_id = subject_id
    inputnode.inputs.freesurfer_dir = str(freesurfer_dir.resolve())

    anatomical_workflow = init_anatomical_wf(
        name="anatomical_wf",
    )
    workflow.connect(
        [
            (
                inputnode,
                anatomical_workflow,
                [
                    ("base_directory", "inputnode.base_directory"),
                    ("atlas_name", "inputnode.atlas_name"),
                    ("atlas_nifti_file", "inputnode.atlas_nifti_file"),
                    ("anatomical_reference", "inputnode.anatomical_reference"),
                    (
                        "mni_to_native_transform",
                        "inputnode.mni_to_native_transform",
                    ),
                    (
                        "gm_probabilistic_segmentation",
                        "inputnode.gm_probabilistic_segmentation",
                    ),
                    ("subject_id", "inputnode.subject_id"),
                    ("freesurfer_dir", "inputnode.freesurfer_dir"),
                ],
            ),
        ]
    )
    if anat_only:
        return workflow
    diffusion_workflows = []
    num_sessions = len(sessions_data)
    diffusion_processing_desc = f"""
    For each of the {num_sessions} DWI runs found per subject {subject_id},
    the following steps were performed:
    """
    for session_inputs in sessions_data.values():
        session_workflow = init_diffusion_wf(dwi_data=session_inputs)
        workflow.connect(
            [
                (
                    inputnode,
                    session_workflow,
                    [
                        ("base_directory", "inputnode.base_directory"),
                        ("atlas_name", "inputnode.atlas_name"),
                        ("anatomical_reference", "inputnode.t1w_file"),
                        ("anatomical_brain_mask", "inputnode.t1w_mask_file"),
                    ],
                ),
                (
                    anatomical_workflow,
                    session_workflow,
                    [
                        (
                            "outputnode.whole_brain_parcellation",
                            "inputnode.whole_brain_t1w_parcellation",
                        ),
                        (
                            "outputnode.gm_cropped_parcellation",
                            "inputnode.gm_cropped_t1w_parcellation",
                        ),
                    ],
                ),
            ]
        )

        diffusion_workflows.append(session_workflow)

    return workflow
