from __future__ import annotations

from .base import ToolRunner
from . import (
    add_chamfer,
    add_fillet,
    attach_reference_image,
    boolean_cut,
    boolean_fuse,
    create_body,
    create_parametric_box,
    create_parametric_cylinder,
    explain_selection,
    export_stl,
    fit_view_selection,
    get_object,
    import_svg_sketch,
    list_document_objects,
    new_sketch,
    pad_sketch,
    pocket_sketch,
    sketch_rectangle,
    transform_placement,
)


def get_runner(name: str) -> ToolRunner | None:
    runners = {
        r.name: r
        for r in (
            explain_selection.RUNNER,
            fit_view_selection.RUNNER,
            list_document_objects.RUNNER,
            get_object.RUNNER,
            attach_reference_image.RUNNER,
            create_parametric_box.RUNNER,
            create_parametric_cylinder.RUNNER,
            transform_placement.RUNNER,
            boolean_cut.RUNNER,
            boolean_fuse.RUNNER,
            add_fillet.RUNNER,
            add_chamfer.RUNNER,
            create_body.RUNNER,
            new_sketch.RUNNER,
            sketch_rectangle.RUNNER,
            pad_sketch.RUNNER,
            pocket_sketch.RUNNER,
            import_svg_sketch.RUNNER,
            export_stl.RUNNER,
        )
    }
    return runners.get(name)
