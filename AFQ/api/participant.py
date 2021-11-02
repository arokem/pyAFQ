import nibabel as nib
from textwrap import dedent

from AFQ.definitions.mapping import SlrMap
from AFQ.api.utils import wf_sections, task_outputs

from AFQ.tasks.data import get_data_plan
from AFQ.tasks.mapping import get_mapping_plan
from AFQ.tasks.tractography import get_tractography_plan
from AFQ.tasks.segmentation import get_segmentation_plan
from AFQ.tasks.viz import get_viz_plan


__all__ = ["ParticipantAFQ"]


class ParticipantAFQ(object):
    def __init__(self,
                 id,
                 dwi_data_file,
                 bval_file, bvec_file,
                 output_dir,
                 **kwargs):
        if not isinstance(output_dir, str):
            raise TypeError(
                "output_dir must be a str")
        if not isinstance(dwi_data_file, str):
            raise TypeError(
                "dwi_data_file must be a str")
        if not isinstance(bval_file, str):
            raise TypeError(
                "bval_file must be a str")
        if not isinstance(bvec_file, str):
            raise TypeError(
                "bvec_file must be a str")
        if not isinstance(id, str):
            raise TypeError(
                "id must be a str")

        img = nib.load(dwi_data_file)
        subses_dict = {
            "id": id,
            "dwi_file": dwi_data_file,
            "results_dir": output_dir}

        input_data = dict(
            subses_dict=subses_dict,
            dwi_img=img,
            dwi_affine=img.affine,
            bval_file=bval_file,
            bvec_file=bvec_file,
            **kwargs)

        # construct pimms plans
        if "mapping" in kwargs and isinstance(kwargs["mapping"], SlrMap):
            plans = {  # if using SLR map, do tractography first
                "data": get_data_plan(kwargs),
                "tractography": get_tractography_plan(kwargs),
                "mapping": get_mapping_plan(kwargs, use_sls=True),
                "segmentation": get_segmentation_plan(kwargs),
                "viz": get_viz_plan(kwargs)}
        else:
            plans = {  # Otherwise, do mapping first
                "data": get_data_plan(kwargs),
                "mapping": get_mapping_plan(kwargs),
                "tractography": get_tractography_plan(kwargs),
                "segmentation": get_segmentation_plan(kwargs),
                "viz": get_viz_plan(kwargs)}

        # chain together a complete plan from individual plans
        previous_data = {}
        for name, plan in plans.items():
            previous_data[f"{name}_imap"] = plan(
                **input_data,
                **previous_data)
            last_name = name

        self.wf_dict =\
            previous_data[f"{last_name}_imap"]

    def __getattribute__(self, attr):
        # check if normal attr exists first
        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            pass

        # find what name to use
        attr_file = attr + "_file"
        if attr in self.wf_dict:
            return self.wf_dict[attr]
        elif attr_file in self.wf_dict:
            return self.wf_dict[attr_file]
        else:
            for sub_attr in wf_sections:
                if attr in self.wf_dict[sub_attr]:
                    return self.wf_dict[sub_attr][attr]
                elif attr_file in self.wf_dict[sub_attr]:
                    return self.wf_dict[sub_attr][attr_file]

        # attr not found, allow typical AttributeError
        return object.__getattribute__(self, attr)


# iterate through all attributes, setting methods for each one
for output, desc in task_outputs.items():
    desc = desc.replace("\n", " ").replace("\t", "").replace("    ", "")
    exec(dedent(f"""\
    def export_{output}(self):
        \"\"\"
        Triggers a cascade of calculations to generate the desired output.
        Returns
        -------
        {desc}
        \"\"\"
        return self.{output}"""))
    fn = locals()[f"export_{output}"]
    if output[-5:] == "_file":
        setattr(ParticipantAFQ, f"export_{output[:-5]}", fn)
    else:
        setattr(ParticipantAFQ, f"export_{output}", fn)
