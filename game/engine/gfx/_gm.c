#include <Python.h>
#include <pygame/pygame.h>

// Python 3 support
#ifndef PyString_FromString
#define PyString_FromString PyUnicode_FromString
#endif

#define MAX_QSORT_LEVELS 300

void quicksort (int *arr, int elements) {
    // http://alienryderflex.com/quicksort/
    int piv, beg[MAX_QSORT_LEVELS], end[MAX_QSORT_LEVELS], i = 0, L, R, swap;
    beg[0] = 0;
    end[0] = elements;
    while (i >= 0) {
        L = beg[i];
        R = end[i] - 1;
        if (L < R) {
            piv = arr[L];
            while (L < R) {
                while (arr[R] >= piv && L < R) R--;
                if (L < R) arr[L++] = arr[R];
                while (arr[L] <= piv && L < R) L++;
                if (L < R) arr[R--] = arr[L];
            }
            arr[L] = piv;
            beg[i + 1] = L + 1;
            end[i + 1] = end[i];
            end[i++] = L;
            if (end[i] - beg[i] > end[i - 1] - beg[i - 1]) {
                swap = beg[i];
                beg[i] = beg[i - 1];
                beg[i - 1] = swap;
                swap = end[i];
                end[i] = end[i - 1];
                end[i - 1] = swap;
            }
        } else i--;
    }
}

int find (int *arr, int n, int x, int i) {
    for (; i < n; i++) {
        if (arr[i] == x) return i;
    }
    return -1;
}

int set_add (int *arr, int n, int x) {
    int i;
    for (i = 0; i < n; i++) {
        if (arr[i] == x) return 0;
    }
    arr[n] = x;
    return 1;
}

PyObject* mk_disjoint (PyObject* add, PyObject* rm) {
    // both arguments are [pygame.Rect]
    int n_rects[2], n_edges[2], i, j, k, l, row0, row1, col0, col1, in_rect,
        r_i, r_left;
    PyRectObject** rects[2];
    GAME_Rect r;
    int* edges[2], * grid;
    PyObject* r_o, * rs;
    // turn into arrays
    add = PySequence_Fast(add, "expected list"); // NOTE: ref[+1]
    rm = PySequence_Fast(rm, "expected list"); // NOTE: ref[+2]
    n_rects[0] = PySequence_Fast_GET_SIZE(add);
    n_rects[1] = PySequence_Fast_GET_SIZE(rm);
    rects[0] = (PyRectObject**) PySequence_Fast_ITEMS(add);
    rects[1] = (PyRectObject**) PySequence_Fast_ITEMS(rm);
    // get edges
    n_edges[0] = 0;
    n_edges[1] = 0;
    i = 2 * (n_rects[0] + n_rects[1]); // max number of edges
    edges[0] = PyMem_New(int, i);
    edges[1] = PyMem_New(int, i); // NOTE: alloc[+1]
    for (i = 0; i < 2; i++) { // rects
        for (j = 0; j < n_rects[i]; j++) { // add|rm
            r = rects[i][j]->r;
            n_edges[0] += set_add(edges[0], n_edges[0], r.x);
            n_edges[0] += set_add(edges[0], n_edges[0], r.x + r.w);
            n_edges[1] += set_add(edges[1], n_edges[1], r.y);
            n_edges[1] += set_add(edges[1], n_edges[1], r.y + r.h);
        }
    }
    // sort edges
    quicksort(edges[0], n_edges[0]);
    quicksort(edges[1], n_edges[1]);
    // generate grid of (rows of) subrects and mark contents
    // each has 2 if add, 1 if rm
    i = (n_edges[0] - 1) * (n_edges[1] - 1);
    grid = PyMem_New(int, i); // NOTE: alloc[+2]
    for (j = 0; j < i; j++) grid[j] = 0;
    for (i = 0; i < 2; i++) { // add|rm
        for (j = 0; j < n_rects[i]; j++) { // rects
            r = rects[i][j]->r;
            if (r.w > 0 && r.h > 0) {
                row0 = find(edges[1], n_edges[1], r.y, 0);
                row1 = find(edges[1], n_edges[1], r.y + r.h, row0);
                col0 = find(edges[0], n_edges[0], r.x, 0);
                col1 = find(edges[0], n_edges[0], r.x + r.w, col0);
                for (k = row0; k < row1; k++) { // rows
                    for (l = col0; l < col1; l++) { // cols
                        if (i == 0) // add
                            grid[(n_edges[0] - 1) * k + l] |= 2;
                        else // rm (i == 1)
                            grid[(n_edges[0] - 1) * k + l] |= 1;
                    }
                }
            }
        }
    }
    // generate subrects
    rs = PyList_New(0);
    in_rect = 0;
    // suppress compiler warnings (we know these will be assigned before use)
    r_i = r_left = 0;
    for (i = 0; i < n_edges[1] - 1; i++) { // rows
        for (j = 0; j < n_edges[0] - 1; j++) { // cols
            if (in_rect && i != r_i) {
                // on a different row: rect ended
                in_rect = 0;
                k = edges[1][r_i];
                // NOTE: ref[+3]
                r_o = PyRect_New4(r_left, k, edges[0][n_edges[0] - 1] - r_left,
                                  edges[1][r_i + 1] - k);
                PyList_Append(rs, r_o);
                Py_DECREF(r_o); // NOTE: ref[-3]
            }
            if (grid[(n_edges[0] - 1) * i + j] == 2) { // add and not rm
                if (!in_rect) {
                    in_rect = 1;
                    r_i = i;
                    r_left = edges[0][j];
                }
            } else if (in_rect) {
                // rect ended
                in_rect = 0;
                k = edges[1][r_i];
                // NOTE: ref[+3]
                r_o = PyRect_New4(r_left, k, edges[0][j] - r_left,
                                  edges[1][r_i + 1] - k);
                PyList_Append(rs, r_o);
                Py_DECREF(r_o); // NOTE: ref[-3]
            }
        }
    }
    if (in_rect) {
        // last rect ended
        k = edges[1][r_i];
        // NOTE: ref[+3]
        r_o = PyRect_New4(r_left, k, edges[0][n_edges[0] - 1] - r_left,
                          edges[1][r_i + 1] - k);
        PyList_Append(rs, r_o);
        Py_DECREF(r_o); // NOTE: ref[-3]
    }
    // cleanup
    PyMem_Free(grid); // NOTE: alloc[-2]
    PyMem_Free(edges[0]);
    PyMem_Free(edges[1]); // NOTE: alloc[-1]
    Py_DECREF(rm); // NOTE: ref[-2]
    Py_DECREF(add); // NOTE: ref[-1]
    return rs;
}

PyObject* fastdraw (PyObject* self, PyObject* args) {
    // don't do much error checking because the point of this is performance
    // and we own the class calling this; guaranteed to get
    // [obj], pygame.Surface, {obj: set(Graphic)}, [pygame.Rect]
    // and layers is sorted
    PyObject* layers_in, * sfc, * graphics_in, * dirty;
    PyObject** layers, *** graphics, ** gs, * g, * g_dirty, * g_rect, * r_o,
            ** graphics_obj, * tmp, * tmp2, * pre_draw, * clip, * vis_tmp[2],
            * rtn, * opaque_in, * dirty_opaque, * l_dirty_opaque,
            ** dirty_by_layer, * rs, * draw_in, * draw;
    char* attrs[4] = {"was_visible", "visible", "_last_postrot_rect",
                      "_postrot_rect"};
    int n_layers, * n_graphics, i, j, k, l, n, n_dirty, r_new, r_good;
    PyRectObject* r, * tmp_r;
    if (!PyArg_UnpackTuple(args, "fastdraw", 4, 4, &layers_in, &sfc,
                           &graphics_in, &dirty))
        return NULL;

    pre_draw = PyString_FromString("_pre_draw"); // NOTE: ref[+1a]
    clip = PyString_FromString("clip"); // NOTE: ref[+1b]
    // get arrays of layers, graphics and sizes
    // NOTE: ref[+2]
    layers_in = PySequence_Fast(layers_in, "layers: expected sequence");
    n_layers = PySequence_Fast_GET_SIZE(layers_in);
    layers = PySequence_Fast_ITEMS(layers_in);
    graphics_obj = PyMem_New(PyObject*, n_layers); // NOTE: alloc[+1]
    n_graphics = PyMem_New(int, n_layers); // NOTE: alloc[+2]
    graphics = PyMem_New(PyObject**, n_layers); // NOTE: alloc[+3]
    for (i = 0; i < n_layers; i++) { // graphics_in
        // NOTE: ref[+3]
        tmp = PySequence_Fast(PyDict_GetItem(graphics_in, layers[i]),
                              "graphics values: expected sequence");
        // need to keep it around since graphics references its array
        graphics_obj[i] = tmp;
        n_graphics[i] = PySequence_Fast_GET_SIZE(tmp);
        graphics[i] = PySequence_Fast_ITEMS(tmp);
    }
    // get dirty rects from graphics
    for (i = 0; i < n_layers; i++) { // graphics
        gs = graphics[i];
        for (j = 0; j < n_graphics[i]; j++) { // gs
            g = gs[j];
            PyObject_CallMethodObjArgs(g, pre_draw, NULL);
            if (PyErr_Occurred() != NULL) return NULL;
            // NOTE: ref[+4] (list)
            g_dirty = PyObject_GetAttrString(g, "_dirty");
            for (k = 0; k < 2; k++) // last/current
                // NOTE: ref[+5]
                vis_tmp[k] = PyObject_GetAttrString(g, attrs[k]);
            if (vis_tmp[0] != vis_tmp[1]) {
                // visiblity changed since last draw: set dirty everywhere
                Py_DECREF(g_dirty); // NOTE: ref[-4]
                g_dirty = PyList_New(1); // NOTE: ref[+4]
                // NOTE: ref[+6]
                g_rect = PyObject_GetAttrString(
                    g, attrs[2 + (vis_tmp[1] == Py_True)]
                );
                PyList_SET_ITEM(g_dirty, 0, g_rect); // NOTE: ref[-6]
            }
            n = PyList_GET_SIZE(g_dirty);
            for (k = 0; k < 2; k++) { // last/current
                if (vis_tmp[k] == Py_True) {
                    // NOTE: ref[+6] (pygame.Rect)
                    g_rect = PyObject_GetAttrString(g, attrs[2 + k]);
                    for (l = 0; l < n; l++) { // g_dirty
                        r_o = PyList_GET_ITEM(g_dirty, l); // pygame.Rect
                        // NOTE: ref[+7]
                        r_o = PyObject_CallMethodObjArgs(r_o, clip, g_rect,
                                                         NULL);
                        PyList_Append(dirty, r_o);
                        Py_DECREF(r_o); // NOTE: ref[-7]
                    }
                    Py_DECREF(g_rect); // NOTE: ref[-6]
                }
            }
            Py_DECREF(vis_tmp[0]);
            Py_DECREF(vis_tmp[1]); // NOTE: ref[-5]
            Py_DECREF(g_dirty); // NOTE: ref[-4]
            tmp = PyObject_GetAttrString(g, "visible"); // NOTE: ref[+4]
            PyObject_SetAttrString(g, "was_visible", tmp);
            Py_DECREF(tmp); // NOTE: ref[-4]
        }
    }

    // only have something to do if dirty is non-empty
    rtn = Py_False;
    Py_INCREF(rtn); // since we're (possibly) returning it
    n_dirty = PyList_GET_SIZE(dirty);
    if (PyList_GET_SIZE(dirty) == 0) {
        goto end;
    }

    opaque_in = PyString_FromString("_opaque_in"); // NOTE: ref[+4]
    dirty_opaque = PyList_New(0); // NOTE: ref[+5]
    dirty_by_layer = PyMem_New(PyObject*, n_layers); // NOTE: alloc[+4]
    for (i = 0; i < n_layers; i++) { // graphics
        gs = graphics[i];
        n = n_graphics[i];
        // get opaque regions of dirty rects
        l_dirty_opaque = PyList_New(0); // NOTE: ref[+6]
        for (j = 0; j < n_dirty; j++) { // dirty
            r = (PyRectObject*) PyList_GET_ITEM(dirty, j); // pygame.Rect
            r_new = 0;
            r_good = 1;
            for (k = 0; k < n; k++) { // gs
                g = gs[k];
                // NOTE: ref[+7]
                g_rect = PyObject_GetAttrString(g, "_postrot_rect");
                if (r_new) tmp_r = r;
                // NOTE: ref[+8]
                r = (PyRectObject*)
                    PyObject_CallMethodObjArgs((PyObject*) r, clip, g_rect,
                                               NULL);
                if (r_new) Py_DECREF(tmp_r); // NOTE: ref[-8](k>0)
                r_new = 1;
                Py_DECREF(g_rect); // NOTE: ref[-7]
                // NOTE: ref[+7]
                tmp = PyObject_CallMethodObjArgs(g, opaque_in, (PyObject*) r,
                                                 NULL);
                if (PyErr_Occurred() != NULL) return NULL;
                r_good = r->r.w > 0 && r->r.h > 0 && \
                         PyObject_RichCompareBool(tmp, Py_True, Py_EQ);
                Py_DECREF(tmp); // NOTE: ref[-7]
                if (!r_good) break;
            }
            if (r_good) PyList_Append(l_dirty_opaque, (PyObject*) r);
            if (r_new) Py_DECREF((PyObject*) r); // NOTE: ref[-8](k=0)
        }
        // undirty below opaque graphics and make dirty rects disjoint
        // NOTE: ref[+7]
        dirty_by_layer[i] = mk_disjoint(dirty, dirty_opaque);
        tmp = dirty_opaque;
        // NOTE: ref[+8] (not sure why this returns a new reference)
        dirty_opaque = PySequence_InPlaceConcat(dirty_opaque, l_dirty_opaque);
        Py_DECREF(tmp); // NOTE: ref[-5] ref[-8+5]
        Py_DECREF(l_dirty_opaque); // NOTE: ref[-6] ref[-7+6]
    }

    draw = PyString_FromString("_draw"); // NOTE: ref[+7]
    // redraw in dirty rects
    for (i = n_layers - 1; i >= 0; i--) { // layers
        rs = dirty_by_layer[i];
        n = PyList_GET_SIZE(rs);
        gs = graphics[i];
        for (j = 0; j < n_graphics[i]; j++) { // gs
            g = gs[j];
            tmp = PyObject_GetAttrString(g, "visible"); // NOTE: ref[+8]
            if (tmp == Py_True) {
                // NOTE: ref[+9]
                g_rect = PyObject_GetAttrString(g, "_postrot_rect");
                draw_in = PyList_New(0); // NOTE: ref[+10]
                for (k = 0; k < n; k++) { // rs
                    r = (PyRectObject*) PyList_GET_ITEM(rs, k);
                    // NOTE: ref[+11]
                    r = (PyRectObject*)
                        PyObject_CallMethodObjArgs(g_rect, clip, r, NULL);
                    if (r->r.w > 0 && r->r.h > 0)
                        PyList_Append(draw_in, (PyObject*) r);
                    Py_DECREF(r); // NOTE: ref[-11]
                }
                if (PyList_GET_SIZE(draw_in) > 0) {
                    PyObject_CallMethodObjArgs(g, draw, sfc, draw_in, NULL);
                    if (PyErr_Occurred() != NULL) return NULL;
                }
                Py_DECREF(draw_in); // NOTE: ref[-10]
                Py_DECREF(g_rect); // NOTE: ref[-9]
            }
            Py_DECREF(tmp); // ref[-8]
            tmp = PyList_New(0); // NOTE: ref[+8]
            PyObject_SetAttrString(g, "_dirty", tmp);
            Py_DECREF(tmp); // NOTE: ref[-8]
        }
    }

    // add up dirty rects to return
    Py_DECREF(rtn);
    rtn = PyList_New(0);
    for (i = 0; i < n_layers; i++) { // dirty_by_layer
        tmp = rtn;
        // NOTE: ref[+8] (not sure why this returns a new reference)
        rtn = PySequence_InPlaceConcat(rtn, dirty_by_layer[i]);
        Py_DECREF(tmp); // NOTE: ref[-8]
    }
    // make all rects disjoint for faster display updating
    tmp = PyList_New(0); // NOTE: ref[+8]
    tmp2 = rtn;
    rtn = mk_disjoint(tmp2, tmp); // NOTE: ref[+9]
    Py_DECREF(tmp2); // NOTE: ref[-9]
    Py_DECREF(tmp); // NOTE: ref[-8]

    // cleanup (in reverse order)
    Py_DECREF(draw); // NOTE: ref[-7]
    // NOTE: ref[-6]
    for (i = 0; i < n_layers; i++) Py_DECREF(dirty_by_layer[i]);
    PyMem_Free(dirty_by_layer); // NOTE: alloc[-4]
    Py_DECREF(dirty_opaque); // NOTE: ref[-5]
    Py_DECREF(opaque_in); // NOTE: ref[-4]
end:
    for (i = 0; i < n_layers; i++) Py_DECREF(graphics_obj[i]); // NOTE: ref[-3]
    PyMem_Free(graphics); // NOTE: alloc[-3]
    PyMem_Free(n_graphics); // NOTE: alloc[-2]
    PyMem_Free(graphics_obj); // NOTE: alloc[-1]
    Py_DECREF(layers_in); // NOTE: ref[-2]
    Py_DECREF(clip); // NOTE: ref[-1b]
    Py_DECREF(pre_draw); // NOTE: ref[-1a]
    return rtn;
}

PyMethodDef methods[] = {
    {"fastdraw", fastdraw, METH_VARARGS,
     "Draw everything; returns dirty list or False."},
    {NULL, NULL, 0, NULL}
};

#if PY_MAJOR_VERSION == 3

// Python 3

static struct PyModuleDef mod = {
    PyModuleDef_HEAD_INIT,
    "_gm", NULL, -1, methods
};

PyMODINIT_FUNC PyInit__gm (void) {
    import_pygame_rect();
    return PyModule_Create(&mod);
}

# else

// Python 2

PyMODINIT_FUNC init_gm (void) {
    import_pygame_rect();
    Py_InitModule("_gm", methods);
}

#endif
