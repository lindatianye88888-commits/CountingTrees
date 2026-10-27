;;; PlantCAD 0.3 / Windows AutoCAD 2007-2014 target (not host-certified).
;;; Base plugin uses AutoLISP; optional AI receiver targets AutoCAD 2014 x64.
(vl-load-com)

(setq pl:*app* "PLANTCAD01" pl:*dict* "PLANTCAD01_DATA" pl:*require-crown* nil)

(defun pl:locate-core (/ path design ai ui workflow project-import)
  (setq path (if (and (boundp 'pl:*dir*) pl:*dir*
    (findfile (strcat pl:*dir* "/plantcad-design.lsp")))
      (findfile (strcat pl:*dir* "/plantcad-core.lsp"))
      (findfile "plantcad-core.lsp")))
  (if (not path) (setq path (getfiled "请选择插件目录内的 plantcad-core.lsp" "plantcad-core.lsp" "lsp" 0)))
  (if path
    (progn
      (setq pl:*dir* (vl-filename-directory path) design (strcat pl:*dir* "/plantcad-design.lsp") ai (strcat pl:*dir* "/plantcad-ai.lsp") ui (strcat pl:*dir* "/plantcad-ui.lsp") workflow (strcat pl:*dir* "/plantcad-workflow.lsp"))
      (setq project-import (strcat pl:*dir* "/plantcad-project-import.lsp"))
      (if (and (findfile design) (findfile ai) (findfile ui) (findfile workflow) (findfile project-import)) (progn (load path) (load design) (load ai) (load ui) (load workflow) (load project-import) T)
        (progn (princ "\n缺少配套的 design、ai、ui、workflow 或 project-import 模块，请完整解压0.3安装包。") nil)))
    (progn (princ "\n未加载核心文件。") nil)))

;;; Keep other add-ons' short command names; full names always use PLANTCAD.
(defun pl:register-command (short canonical / symbol)
  (setq symbol (strcat "C:" short))
  (if (and (boundp 'pl:*enable-short-commands*) pl:*enable-short-commands*
    (not (or (getcname short) (car (atoms-family 1 (list symbol))))))
    (eval (list 'defun (read symbol) nil
      (list (read (strcat "C:" canonical)))))))

(defun pl:doc () (vla-get-ActiveDocument (vlax-get-acad-object)))

(defun pl:fail (message)
  (setq pl:*failure* message) (exit))

(defun pl:cancelled-error-p (message)
  (and (= (type message) 'STR)
    (or (vl-string-search "CANCEL" (strcase message))
        (vl-string-search "QUIT / EXIT ABORT" (strcase message))
        (vl-string-search "CONSOLE BREAK" (strcase message))
        (vl-string-search "USER BREAK" (strcase message))
        (vl-string-search "取消" message))))

(defun pl:rethrow (result / message)
  ;; Keep pl:fail's original reason through nested catch/cleanup; exit's text is not the reason.
  (setq message (vl-catch-all-error-message result))
  (if (and (not pl:*failure*) (not (pl:cancelled-error-p message))) (setq pl:*failure* message))
  (exit))

(defun pl:report-error (result / message)
  (setq message (vl-catch-all-error-message result))
  (if (and (not pl:*failure*) (pl:cancelled-error-p message))
    (princ "\nCountingTrees（数树）：操作已取消。")
    (progn
      (setq pl:*failure* (if pl:*failure* pl:*failure* message))
      (if pl:*stage* (setq pl:*failure* (strcat pl:*stage* "：" pl:*failure*)))
      (princ (strcat "\nCountingTrees（数树）：" pl:*failure* "；已有改动可用 U 撤销。"))
      (alert (strcat "CountingTrees（数树）：" pl:*failure* "\n已有改动可用 U 撤销；完整原因已写入命令行。")))))

(defun pl:run (fn / doc result)
  ;; COM undo marks also work on errors; no command calls in *error*.
  (setq doc (pl:doc) pl:*failure* nil pl:*stage* nil pl:*drawing-changed* nil)
  (vla-StartUndoMark doc)
  (setq result (vl-catch-all-apply fn nil))
  (if (and (not (vl-catch-all-error-p result)) (pl:run-needs-sync fn))
    (setq result (vl-catch-all-apply 'pl:sync-drawing nil)))
  (vl-catch-all-apply 'vla-EndUndoMark (list doc))
  (if (vl-catch-all-error-p result) (pl:report-error result))
  (setq pl:*stage* nil)
  (princ))

(defun pl:db-get (key default)
  (vlax-ldata-get pl:*dict* key default))

(defun pl:db-put (key value)
  (if (member key '("PLANTS" "PLOT_OPTIONS" "UNIT" "UNITS_PER_M")) (setq pl:*drawing-changed* T))
  (vlax-ldata-put pl:*dict* key value))

(defun pl:data-get (e key)
  (vlax-ldata-get (vlax-ename->vla-object e) key nil))

(defun pl:data-put (e key value)
  (if (member key '("PLANT" "AREA_PLANT" "UNITS" "PROJECT_PLANT" "PROJECT_COUNT")) (setq pl:*drawing-changed* T))
  (vlax-ldata-put (vlax-ename->vla-object e) key value))

(defun pl:defs (/ result p)
  (foreach p (pl:db-get "PLANTS" nil) (setq result (append result (list (pl:upgrade-plant p))))) result)

(defun pl:by-id (id / result p)
  (foreach p (pl:defs) (if (= id (pl:get 'id p)) (setq result p))) result)

(defun pl:save-def (p / defs old)
  (setq defs (pl:defs) old (pl:by-id (pl:get 'id p)))
  (pl:remember-spec p) (pl:remember-size p)
  (pl:db-put "PLANTS" (if old (subst p old defs) (append defs (list p)))))

(defun pl:new-id (/ seq)
  (setq seq (1+ (pl:db-get "SEQUENCE" 0)))
  (pl:db-put "SEQUENCE" seq)
  (strcat "P" (rtos (getvar "DATE") 2 8) "_" (itoa seq)))

(defun pl:current () (pl:by-id (pl:db-get "CURRENT" "")))

(defun pl:unit-index (/ u)
  (setq u (pl:db-get "UNIT" -1))
  (if (member u '(0 1 2 3)) u -1))

(defun pl:units (/ index)
  (setq index (pl:unit-index))
  (if (= index 3) (pl:db-get "UNITS_PER_M" nil)
    (if (>= index 0) (nth index '(1000.0 1.0 100.0)) nil)))

(defun pl:settings-work () (pl:design-settings))

(defun pl:require-units ()
  (if (< (pl:unit-index) 0) (pl:settings-work))
  (if (< (pl:unit-index) 0)
    (progn (princ "\n图纸单位尚未确认，操作取消。") nil) T))

(defun pl:layers ()
  '(("PL_树木_圆圈" 3 T) ("PL_树木_简化" 3 T)
    ("PL_灌木球_圆圈" 3 T) ("PL_灌木球_简化" 3 T) ("PL_灌木球_标注" 7 T)
    ("PL_花境_图例" 4 T) ("PL_花境_填充" 4 T) ("PL_花境_标注" 7 T)
    ("PL_灌木_标注" 7 T) ("PL_草地_标注" 7 T) ("PL_辅助_填充边界" 8 nil)
    ("PL_灌木_原始线" 2 T) ("PL_灌木_计算边界" 2 T)
    ("PL_灌木_填充" 8 T) ("PL_草地_边界" 8 T)
    ("PL_草地_填充" 3 T) ("PL_标注_树木" 7 T)
    ("PL_标注_区域" 7 T) ("PL_表格_苗木" 7 T)
    ("PL_表格_植物名录" 7 T) ("PL_表格_植物规格" 7 T)
    ("PL_表格_面积" 7 T) ("PL_面积_计算边界" 2 T) ("PL_面积_推定补线" 1 T) ("PL_辅助_缺口检查" 1 nil)))

(defun pl:migrate-shrub-colors (/ name ed obj)
  (if (not (pl:db-get "SHRUB_COLOR_REV" nil))
    (progn
      (foreach name '("PL_灌木_原始线" "PL_灌木_计算边界")
        (setq ed (tblsearch "LAYER" name))
        (if (and ed (member (cdr (assoc 62 ed)) '(3 8)))
          (progn (setq obj (vla-Item (vla-get-Layers (pl:doc)) name)) (vla-put-Color obj 2))))
      (pl:db-put "SHRUB_COLOR_REV" 1)))
  (if (not (pl:db-get "SHRUB_FILL_GRAY_REV" nil))
    (progn
      (setq name "PL_灌木_填充" ed (tblsearch "LAYER" name))
      (if (and ed (not (assoc 420 ed)) (member (cdr (assoc 62 ed)) '(2 3))
        (= 0 (logand 4 (cdr (assoc 70 ed)))))
        (vla-put-Color (vla-Item (vla-get-Layers (pl:doc)) name) 8))
      (pl:db-put "SHRUB_FILL_GRAY_REV" 1))))

(defun pl:init-layers (/ layers row obj n)
  (setq layers (vla-get-Layers (pl:doc)) n 0)
  (foreach row (pl:layers)
    (if (not (tblsearch "LAYER" (car row)))
      (progn
        (setq obj (vla-Add layers (car row)))
        (vla-put-Color obj (cadr row))
        (vla-put-Linetype obj "Continuous")
        (vla-put-Plottable obj (if (caddr row) :vlax-true :vlax-false))
        (setq n (1+ n)))))
  (pl:migrate-shrub-colors)
  (regapp pl:*app*) n)

(defun pl:layer-open (name / ed)
  (setq ed (tblsearch "LAYER" name))
  (and ed (= 0 (logand 4 (cdr (assoc 70 ed))))))

(defun pl:writable (e)
  (and (entget e) (pl:layer-open (cdr (assoc 8 (entget e))))))

(defun pl:make (data / ok)
  ;; entmake gives ordinary graphics a database owner; do not use ownerless entmakex.
  (setq ok (entmake data))
  (if ok (entlast) (pl:fail "CAD拒绝创建对象。")))

(defun pl:mark (e role handle / ed payload)
  (regapp pl:*app*)
  (setq ed (entget e) payload (list pl:*app* (cons 1000 role)))
  (if handle (setq payload (append payload (list (cons 1005 handle)))))
  (if (not (entmod (append ed (list (list -3 payload)))))
    (pl:fail "无法保存对象关联。")) e)

(defun pl:xdata (e)
  (cadr (assoc -3 (entget e (list pl:*app*)))))

(defun pl:role (e) (cdr (assoc 1000 (cdr (pl:xdata e)))))

(defun pl:source (e / h)
  (setq h (cdr (assoc 1005 (cdr (pl:xdata e)))))
  (if h (handent h)))

(defun pl:plant (e / p def)
  (if (and (= (cdr (assoc 0 (entget e))) "INSERT") (equal (pl:role e) "TREE"))
    (if (setq p (pl:data-get e "PLANT"))
      (progn
        (setq p (pl:upgrade-plant p))
        (if (and (= (pl:get 'spec_no p) "") (setq def (pl:by-id (pl:get 'id p))))
          (setq p (pl:put 'spec_no (pl:get 'spec_no def) p))) p))))

(defun pl:ss-list (ss / i result)
  (setq i 0 result nil)
  (if ss
    (repeat (sslength ss)
      (setq result (cons (ssname ss i) result) i (1+ i))))
  (reverse result))

(defun pl:all-trees (/ e result)
  (if (assoc 'trees pl:*entity-cache*) (cdr (assoc 'trees pl:*entity-cache*))
  (progn
  (foreach e (pl:ss-list (ssget "_X" '((0 . "INSERT") (-3 ("PLANTCAD01")))))
    (if (pl:plant e) (setq result (cons e result))))
  (reverse result))))

(defun pl:select-trees (/ e result)
  (princ "\n选择本插件生成的树木图块：")
  (foreach e (pl:ss-list (ssget '((0 . "INSERT") (-3 ("PLANTCAD01")))))
    (if (pl:plant e) (setq result (cons e result))))
  (reverse result))

(defun pl:all-labels ()
  (if (assoc 'labels pl:*entity-cache*) (cdr (assoc 'labels pl:*entity-cache*))
    (pl:ss-list (ssget "_X" '((0 . "MTEXT,MULTILEADER") (-3 ("PLANTCAD01")))))))

(defun pl:dialog (name / path id)
  (setq path (strcat pl:*dir* "/plantcad.dcl") id (load_dialog path))
  (if (and (>= id 0) (new_dialog name id)) id
    (progn
      (if (>= id 0) (unload_dialog id))
      (princ "\n对话框加载失败，请确认 plantcad.dcl 与插件在同一目录。") nil)))

(defun pl:popup (key values / value)
  (start_list key) (foreach value values (add_list value)) (end_list))

(defun pl:fill-edit (p / key units value)
  (set_tile "name" (pl:get 'name p)) (set_tile "spec_no" (pl:get 'spec_no p))
  (set_tile "plant_identity" (strcat "当前树种：" (pl:get 'name p) "    规格：" (pl:get 'spec_no p)))
  (pl:popup "kind" (pl:kind-names))
  (pl:edit-name-choices p)
  (pl:popup "fill_pattern" (cons "自动按植物种类" (pl:fill-patterns)))
  (set_tile "fill_pattern" (itoa (pl:fill-pattern-index (pl:get 'fill_pattern p))))
  (set_tile "fill_scale" (pl:num (* 100.0 (pl:get 'fill_scale p))))
  (set_tile "fill_angle" (rtos (pl:get 'fill_angle p) 2 2))
  (pl:popup "style" '("圆圈" "简笔树冠外框" "自定义普通图块"))
  (pl:popup "diameter_mode" '("胸径（D / cm）" "地径（d / cm）"))
  (pl:popup "quantity_unit" '("株" "丛" "平方米（面积规格）"))
  (set_tile "quantity_unit" (cond ((= (pl:get 'quantity_unit p) "平方米") "2") ((= (pl:get 'quantity_unit p) "丛") "1") (T "0")))
  (set_tile "diameter_mode" (itoa (pl:get 'diameter_mode p)))
  (set_tile "kind" (itoa (pl:get 'kind p))) (set_tile "style" (itoa (pl:get 'style p)))
  (set_tile "block" (pl:get 'block p))
  (foreach key '(dbh caliper height crown)
    (set_tile (strcase (vl-symbol-name key) T) (pl:dimension-text key p)))
  (set_tile "factor" (pl:num (pl:get 'factor p)))
  (setq units (pl:units))
  (set_tile "base" (if units (pl:num (/ (* (pl:get 'base p) 100.0) units)) ""))
  (pl:edit-kind-change (itoa (pl:get 'kind p)))
  (pl:dialog-preview (itoa (pl:get 'style p))))

(defun pl:edit-kind-change (value / key text)
  (foreach key '("dbh" "caliper")
    (setq text (get_tile key))
    (if (or (= text "") (= text "0")) (set_tile key "——"))))

(defun pl:accept-edit (/ p key s n msg units)
  (setq p pl:*edit* msg nil)
  (setq p (pl:put 'name (pl:trim (get_tile "name")) p)
        p (pl:put 'spec_no (pl:trim (get_tile "spec_no")) p)
        p (pl:put 'kind (atoi (get_tile "kind")) p)
        p (pl:put 'diameter_mode (atoi (get_tile "diameter_mode")) p)
        p (pl:put 'quantity_unit (nth (atoi (get_tile "quantity_unit")) '("株" "丛" "平方米")) p)
        p (pl:put 'style (atoi (get_tile "style")) p)
        p (pl:put 'block (pl:trim (get_tile "block")) p))
  (foreach key '(dbh caliper height crown factor base)
    (setq s (pl:trim (get_tile (strcase (vl-symbol-name key) T))))
    (setq n
      (cond
        ((= key 'factor) (pl:number-input s))
        ((= key 'base)
          (if (= (pl:get 'style p) 2)
            (if (and (setq units (pl:units)) (pl:number-input s))
              (* (/ (pl:number-input s) 100.0) units) nil)
            (pl:get 'base p)))
        (T (pl:dimension-input key s (pl:get 'kind p)))))
    (if (null n) (setq msg "尺寸请填写cm数值；未填写的指标可留空或填——。自定义块需先确认底图单位。")
      (setq p (pl:put key n p))))
  (cond ((and (<= (pl:get 'dbh p) 0) (> (pl:get 'caliper p) 0)) (setq p (pl:put 'diameter_mode 1 p)))
        ((and (> (pl:get 'dbh p) 0) (<= (pl:get 'caliper p) 0)) (setq p (pl:put 'diameter_mode 0 p))))
  (if (not msg) (setq msg (pl:plant-error p)))
  (if (and (not msg) pl:*require-crown*) (setq msg (pl:insert-error p)))
  (if (not msg) (setq msg (pl:accept-fill-fields)))
  (if (not msg) (setq p (pl:put 'fill_pattern pl:*fill-pattern* (pl:put 'fill_scale pl:*fill-scale* (pl:put 'fill_angle pl:*fill-angle* p)))))
  (if (and (not msg) (not pl:*project-edit*)) (setq p (pl:prepare-edited-spec p pl:*edit* (pl:used-specs))))
  (if (not msg) (setq msg (pl:spec-error p (pl:used-specs))))
  (if (and (not msg) (not pl:*project-edit*)) (setq msg (pl:history-error p)))
  (if (and (not msg) (= (pl:get 'style p) 2)) (setq msg (pl:custom-error (pl:get 'block p))))
  (if msg (progn (set_tile "error" msg) (if (<= (pl:get 'crown p) 0) (mode_tile "crown" 2)))
    (progn (setq pl:*edit-result* p) (done_dialog 1))))

(defun pl:edit-dialog-start (p)
      ;; Bind cancellation before populating lists or reading drawing data.
      (action_tile "cancel" "(setq pl:*edit-result* nil) (done_dialog 0)")
      (action_tile "accept" "(pl:accept-edit)")
      (action_tile "style" "(pl:dialog-preview $value)")
      (action_tile "kind" "(pl:edit-kind-change $value)")
      (action_tile "plant_choice" "(pl:edit-name-selected $value)")
      (pl:fill-edit p)
      (if (and pl:*require-crown* (<= (pl:get 'crown p) 0))
        (progn (set_tile "error" "请先补填当前植物的实际冠幅（cm），再开始布置。") (mode_tile "crown" 2)))
      (start_dialog))

(defun pl:edit-dialog (p / id status)
  (setq p (pl:upgrade-plant p) id (pl:dialog "pl_edit") pl:*edit* p pl:*edit-result* nil)
  (if id
    (progn
      ;; NEW_DIALOG already creates a native window. An initialization error
      ;; must dismiss it before the command's outer error handler resumes.
      (setq status (vl-catch-all-apply 'pl:edit-dialog-start (list p)))
      (if (vl-catch-all-error-p status)
        (progn (setq pl:*edit-result* nil) (vl-catch-all-apply 'term_dialog nil)))
      (unload_dialog id)
      (if (vl-catch-all-error-p status) (pl:rethrow status))
      (if (= status 1)
        (progn
          (if (/= (pl:get 'spec_no p) (pl:get 'spec_no pl:*edit-result*))
            (princ (strcat "\n当前规格编号：" (pl:get 'spec_no pl:*edit-result*))))
          pl:*edit-result*) (progn (setq pl:*edit-result* nil) nil)))))

(defun pl:custom-error (name / block obj ed)
  (setq block (tblsearch "BLOCK" name))
  (cond
    ((not block) "本图中找不到该图块，请先用INSERT导入，再填写名称。")
    ((/= 0 (logand 12 (cdr (assoc 70 block)))) "不能使用外部参照，请选普通图块。")
    (T
      (setq obj (vla-Item (vla-get-Blocks (pl:doc)) name))
      (vlax-for ed obj
        (if (= (vla-get-ObjectName ed) "AcDbAttributeDefinition")
          (setq block "自定义原始图块不能带属性；插件会自动添加名称和径值。")))
      (if (eq (type block) 'STR) block nil))))

(defun pl:library-work () (pl:design-library))

(defun pl:built-blocks (/ name pts i a r)
  (foreach name '("PL02_CIRCLE" "PL02_SIMPLE")
    (if (not (tblsearch "BLOCK" name))
      (progn
        (if (not (entmake (list '(0 . "BLOCK") (cons 2 name) '(70 . 2)
                                 '(8 . "0") '(10 0.0 0.0 0.0))))
          (pl:fail "无法创建图例图块。"))
        (if (= name "PL02_CIRCLE")
          (entmake '((0 . "CIRCLE") (8 . "0") (62 . 0) (10 0.0 0.0 0.0) (40 . 0.5)))
          (progn
            ;; Radial lobes, baseline external diameter exactly 1.
            (setq pts nil i 0)
            (repeat 48
              (setq a (* 2.0 pi (/ i 48.0)) r (- 0.5 (* 0.055 (- 1.0 (cos (* 8.0 a))))))
              (setq pts (append pts (list (cons 10 (list (* r (cos a)) (* r (sin a))))))
                    i (1+ i)))
            (entmake (append '((0 . "LWPOLYLINE") (100 . "AcDbEntity") (8 . "0")
                  (62 . 0) (100 . "AcDbPolyline") (90 . 48) (70 . 1)) pts))
            (entmake '((0 . "CIRCLE") (8 . "0") (62 . 0) (10 0.0 0.0 0.0) (40 . 0.055)))))
        (pl:symbol-attdefs)
        (entmake '((0 . "ENDBLK") (8 . "0")))))))

(defun pl:block-name (p)
  (if (= (pl:get 'style p) 2) (pl:custom-wrapper p)
    (nth (pl:get 'style p) '("PL02_CIRCLE" "PL02_SIMPLE"))))

(defun pl:tree-layer (p)
  (cond ((= (pl:get 'kind p) 3) (if (= (pl:get 'style p) 0) "PL_灌木球_圆圈" "PL_灌木球_简化"))
    ((= (pl:get 'kind p) 4) "PL_花境_图例")
    (T (if (= (pl:get 'style p) 0) "PL_树木_圆圈" "PL_树木_简化"))))

(defun pl:space ()
  (if (or (= (getvar "TILEMODE") 1) (> (getvar "CVPORT") 1))
    (vla-get-ModelSpace (pl:doc)) (vla-get-PaperSpace (pl:doc))))

(defun pl:insert-work (/ p msg point obj e scale units)
  (pl:init-layers)
  (if (not (pl:current)) (pl:design-start))
  (setq p (pl:current))
  (if p (setq p (pl:resolve-placement p)))
  (if p
    (progn
      (setq msg (pl:insert-error p))
      (if msg (alert msg)
        (if (pl:require-units)
          (progn
            (pl:built-blocks)
            (setq units (pl:units) scale (pl:block-scale p units))
            (if (setq msg (pl:layer-issue (pl:tree-layer p))) (pl:fail msg))
            (princ (strcat "\n布置 " (pl:get 'name p) "；显示直径="
                           (pl:num (pl:diameter p units)) " 图纸单位。回车结束。"))
            (while (setq point (pl:pick-placement p units))
              (setq point (trans point 1 0))
              (setq obj (pl:insert-symbol p point scale))
              (vla-put-Layer obj (pl:tree-layer p))
              (vla-put-Color obj 256)
              (setq e (vlax-vla-object->ename obj))
              (pl:mark e "TREE" nil)
              (pl:data-put e "PLANT" p)
              (pl:data-put e "UNITS" units)
              (if (not (pl:refresh-symbol e)) (pl:fail "图块未生成内部文字属性，请检查图例定义。")))))))))

(defun pl:set-dxf (code value data / pair)
  (if (setq pair (assoc code data)) (subst (cons code value) pair data)
    (append data (list (cons code value)))))

(defun pl:apply-plant (e p / ed scale units)
  (if (and (pl:writable e) (pl:layer-open (pl:tree-layer p))
           (not (pl:insert-error p)))
    (progn
      (setq units (pl:data-get e "UNITS"))
      (if (and units (> units 0))
        (progn
          (setq scale (pl:block-scale p units) ed (entget e))
          ;; entmod preserves handle/base point/rotation, maintaining label links.
          (setq ed (pl:set-dxf 2 (pl:block-name p) ed)
                ed (pl:set-dxf 8 (pl:tree-layer p) ed)
                ed (pl:set-dxf 41 scale ed)
                ed (pl:set-dxf 42 scale ed)
                ed (pl:set-dxf 43 scale ed))
          (if (entmod ed)
            (progn (pl:data-put e "PLANT" p) (entupd e) (pl:refresh-symbol e) T) nil)))) nil))

(defun pl:update-from-def (p / scope targets e n skipped count answer)
  (if (pl:insert-error p) (alert (pl:insert-error p))
    (progn
      (initget "Selected All Cancel")
      (setq scope (getkword "\n更新范围 [所选(Selected)/当前图同定义全部(All)/取消(Cancel)] <Cancel>："))
      (cond
        ((= scope "Selected")
          (foreach e (pl:select-trees)
            (if (= (pl:get 'id (pl:plant e)) (pl:get 'id p))
              (setq targets (cons e targets)))))
        ((= scope "All")
          (foreach e (pl:all-trees)
            (if (= (pl:get 'id (pl:plant e)) (pl:get 'id p))
              (setq targets (cons e targets))))))
      (if targets
        (progn
          (princ (strcat "\n将更新 " (itoa (length targets)) " 株，应用当前定义的名称、规格和图例。"))
          (initget "Yes No")
          (setq answer (getkword "\n执行 [是(Yes)/否(No)] <No>："))
          (if (= answer "Yes")
            (progn
              (pl:built-blocks) (setq n 0 skipped 0)
              (foreach e targets
                (if (pl:apply-plant e p) (setq n (1+ n)) (setq skipped (1+ skipped))))
              (pl:sync-labels)
              (princ (strcat "\n已更新 " (itoa n) " 株；跳过锁定或无效对象 " (itoa skipped) " 株。")))))
        (princ "\n未选中符合该植物定义的树木，或操作取消。")))))

(defun pl:update-work (/ p)
  (setq p (pl:current))
  (if p (pl:update-from-def p) (alert "请先用 PLPLANT 选择当前植物。")))

(defun pl:size-work (/ targets mode value e p n skipped)
  (setq targets (pl:select-trees))
  (if targets
    (progn
      (initget "Crown Display")
      (setq mode (getkword "\n调整 [真实冠幅cm(Crown)/显示系数(Display)] <Crown>："))
      (if (not mode) (setq mode "Crown"))
      (initget 6)
      (setq value (getreal (if (= mode "Crown") "\n新的实际冠幅 / cm：" "\n新的显示系数：")))
      (if value
        (progn
          (if (= mode "Crown") (setq value (/ value 100.0)))
          (pl:built-blocks) (setq n 0 skipped 0)
          (foreach e targets
            (setq p (pl:put (if (= mode "Crown") 'crown 'factor) value (pl:plant e)))
            (if (and (= mode "Crown") (pl:writable e)) (setq p (pl:instance-variant p)))
            (if (pl:apply-plant e p) (setq n (1+ n)) (setq skipped (1+ skipped))))
          (pl:sync-labels)
          (princ (strcat "\n已调整 " (itoa n) " 株；跳过 " (itoa skipped) " 株。")))))))

(defun pl:style-work (/ targets value e p n skipped)
  (setq targets (pl:select-trees))
  (if targets
    (progn
      (initget "Circle Simple")
      (setq value (getkword "\n图例 [圆圈(Circle)/简化(Simple)] <Circle>："))
      (pl:built-blocks) (setq n 0 skipped 0)
      (foreach e targets
        (setq p (pl:put 'style (if (= value "Simple") 1 0) (pl:plant e)))
        (if (pl:apply-plant e p) (setq n (1+ n)) (setq skipped (1+ skipped))))
      (princ (strcat "\n已切换 " (itoa n) " 株；跳过 " (itoa skipped) " 株。")))))

(defun pl:label-options (/ id result opts units)
  (if (not (pl:require-units)) (pl:fail "请先确认底图单位。"))
  (setq units (pl:units))
  (setq opts (pl:db-get "LABEL_OPTIONS"
    (list (cons 'mode 1) (cons 'prefix 0) (cons 'units 0)
          (cons 'height (pl:paper-height 2.5 (pl:get 'scale (pl:db-get "PLOT_OPTIONS" '((scale . 100.0)))) units)) (cons 'leader 1))))
  (setq id (pl:dialog "pl_label") pl:*label-result* nil)
  (if id
    (progn
      (pl:popup "mode" '("仅名称" "名称 + 下行胸径/地径数字" "名称 + 下行完整规格" "规格编号"))
      (pl:popup "prefix" '("12（纯数字）" "D12" "D=12"))
      (set_tile "mode" (itoa (pl:get 'mode opts)))
      (set_tile "prefix" (itoa (pl:get 'prefix opts)))
      (set_tile "units" (itoa (pl:get 'units opts)))
      (set_tile "leader" (itoa (pl:get 'leader opts)))
      (set_tile "height" (pl:num (/ (* (pl:get 'height opts) 100.0) units)))
      (action_tile "accept" "(pl:accept-label)")
      (action_tile "cancel" "(done_dialog 0)")
      (setq result (start_dialog)) (unload_dialog id)
      (if (= result 1)
        (progn (pl:db-put "LABEL_OPTIONS" pl:*label-result*) pl:*label-result*) nil))))

(defun pl:accept-label (/ height)
  (setq height (pl:number-input (get_tile "height")))
  (if (and height (> height 0))
    (progn
      (setq pl:*label-result* (list
        (cons 'mode (atoi (get_tile "mode")))
        (cons 'prefix (atoi (get_tile "prefix")))
        (cons 'units (atoi (get_tile "units")))
        (cons 'leader (atoi (get_tile "leader"))) (cons 'height (* (/ height 100.0) (pl:units)))))
      (done_dialog 1))
    (set_tile "error" "文字高度必须是大于0的十进制数字。")))

(defun pl:linked (tree / h e result)
  (setq h (cdr (assoc 5 (entget tree))))
  (if pl:*entity-cache* (cdr (assoc h pl:*link-cache*))
  (progn
  (foreach e (pl:ss-list (ssget "_X" '((-3 ("PLANTCAD01")))))
    (if (and (member (pl:role e) '("LABEL" "LEADER"))
             (equal h (cdr (assoc 1005 (cdr (pl:xdata e))))))
      (setq result (cons e result)))) result)))

(defun pl:new-label (tree point opts / p h label line pos)
  (setq p (pl:plant tree) h (cdr (assoc 5 (entget tree))))
  (if (pl:layer-issue (pl:plant-label-layer p)) (pl:fail (pl:layer-issue (pl:plant-label-layer p))))
  (setq label (pl:make (list '(0 . "MTEXT") '(100 . "AcDbEntity")
    (cons 8 (pl:plant-label-layer p)) '(62 . 256) '(100 . "AcDbMText")
    (cons 10 point) (cons 40 (pl:get 'height opts)) '(41 . 0.0)
    '(71 . 2) '(72 . 1) (cons 1 (strcat "\\qc;" (pl:label-text p opts)))
    (cons 7 (getvar "TEXTSTYLE")) '(11 1.0 0.0 0.0))))
  (pl:mark label "LABEL" h) (pl:data-put label "OPTIONS" opts)
  (if (= (pl:get 'leader opts) 1)
    (progn
      (setq pos (trans (cdr (assoc 10 (entget tree))) tree 0))
      (setq line (pl:make (list '(0 . "LINE") (cons 8 (pl:plant-label-layer p))
                        '(62 . 256) (cons 10 pos) (cons 11 point))))
      (pl:mark line "LEADER" h))) label)

(defun pl:label-work (/ pick tree point opts old e safe)
  (pl:init-layers)
  (if (setq opts (pl:label-options))
    (while (setq pick (entsel "\n点选需要标注的植物图块，回车结束："))
      (setq tree (car pick))
      (if (pl:plant tree)
        (if (setq point (getpoint (cadr pick) "\n名称标注位置："))
          (progn
            (setq old (pl:linked tree) safe T)
            (foreach e old (if (not (pl:writable e)) (setq safe nil)))
            (if safe
              (progn
                ;; Create successfully before removing previous annotation.
                (pl:new-label tree (trans point 1 0) opts)
                (foreach e old (entdel e)))
              (princ "\n已有标注或引线图层锁定，已跳过。"))))
        (princ "\n这不是本插件的植物图块。")))))

(defun pl:sync-labels (/ label tree p opts ed n orphan skipped line pos endpoint changed)
  (pl:refresh-all-symbols)
  (pl:sync-area-labels)
  (setq n 0 orphan 0 skipped 0)
  (foreach label (pl:all-labels)
    (if (equal (pl:role label) "LABEL")
      (progn
        (setq tree (pl:source label) p (if tree (pl:plant tree)))
        (cond
          ((not p) (setq orphan (1+ orphan)))
          ((not (pl:writable label)) (setq skipped (1+ skipped)))
          (T
            (setq opts (pl:data-get label "OPTIONS"))
            (if opts
              (progn
                (setq ed (entget label))
                (setq ed (pl:set-dxf 8 (pl:plant-label-layer p) (pl:set-dxf 1 (strcat "\\qc;" (pl:label-text p opts)) ed)))
                (setq changed (not (equal ed (entget label))))
                (if (or (not changed) (entmod ed))
                  (progn
                    (if changed (progn (entupd label) (setq n (1+ n))))
                    (setq pos (trans (cdr (assoc 10 (entget tree))) tree 0)
                          endpoint (cdr (assoc 10 (entget label))))
                    (foreach line (pl:linked tree)
                      (if (and (equal (pl:role line) "LEADER") (pl:writable line))
                        (progn
                          (setq ed (pl:set-dxf 8 (pl:plant-label-layer p) (pl:set-dxf 11 endpoint
                                   (pl:set-dxf 10 pos (entget line)))))
                          (if (not (equal ed (entget line))) (entmod ed))))))
                  (setq skipped (1+ skipped))))
              (setq skipped (1+ skipped))))))))
  (princ (strcat "\n标注刷新 " (itoa n) " 项；失去植物关联 " (itoa orphan)
                 " 项；锁定或无效 " (itoa skipped) " 项。")))

(defun pl:rename-work (/ trees name e p n rows ids d)
  ;; Explicitly confirmed spelling/alias changes. Preserve every instance's real specs.
  (setq trees (pl:select-trees))
  (if trees
    (progn
      (setq name (pl:trim (getstring T "\n将所选树木统一为植物名称（请保留品种信息）：")))
      (if (and (/= name "") (<= (strlen name) 80))
        (progn
          (setq n 0)
          (foreach e trees
            (if (pl:writable e)
              (progn
                (setq p (pl:put 'name name (pl:plant e)))
                (setq p (pl:instance-variant p))
                (pl:data-put e "PLANT" p) (setq n (1+ n)))))
          (pl:sync-labels)
          (princ (strcat "\n已统一 " (itoa n) " 株的名称，原胸径、高度、冠幅保留。"
                         "植物库默认名称请另用 PLPLANT 修改。")))
        (princ "\n名称为空或过长，已取消。")))))

(defun pl:count-rows (objects / rows e quantity)
  (foreach e objects
    (if (setq quantity (pl:quantity-data e))
      (setq rows (pl:add-quantity (car quantity) (cadr quantity) rows)))) (pl:sort-count-rows rows))

(defun pl:count-work (/ scope trees rows row p total area handles skipped pending quantity)
  (pl:import-area-label-edits)
  (setq scope (if (boundp 'pl:*count-scope*) pl:*count-scope* nil) pl:*count-scope* nil)
  (if (not scope)
    (progn
      (initget "Selected Model")
      (setq scope (getkword "\n统计 [所选(Selected)/全部模型空间(Model)] <Selected>："))))
  (setq trees (if (= scope "Model") (pl:statistics-model) (pl:statistics-select))
        rows (pl:count-rows trees) total 0 area 0.0 skipped 0 pending 0)
  (princ "\n编号 | 植物名称 | 胸径cm | 地径cm | 高度cm | 冠幅cm | 数量 | 单位")
  (foreach row rows
    (setq p (cadr row))
    (if (= (pl:get 'quantity_unit p) "平方米") (setq area (+ area (caddr row)))
      (setq total (+ total (caddr row))))
    (princ (strcat "\n" (pl:get 'spec_no p) " | " (pl:get 'name p) " | "
      (pl:dimension-text 'dbh p) " | " (pl:dimension-text 'caliper p) " | "
      (pl:dimension-text 'height p) " | " (pl:dimension-text 'crown p) " | "
      (pl:quantity-text p (caddr row)) " | " (pl:get 'quantity_unit p))))
  (foreach row trees
    (if (or (pl:quantity-data row) (equal (pl:role row) "PROJECT_SOURCE"))
      (progn
        (setq handles (append handles (list (cdr (assoc 5 (entget row))))))
        (if (not (pl:quantity-data row)) (setq pending (1+ pending))))
      (setq skipped (1+ skipped))))
  (princ (strcat "\n单株/丛图例：" (itoa total) " 个；种植范围：" (pl:area-text area)
    " 平方米；仅名称待关联 " (itoa pending) " 个；失效范围跳过 " (itoa skipped) " 个。"))
  (princ "\n统计完成，可指定位置生成带图例、编号的关联表。")
  (pl:db-put "LAST_COUNT_SCOPE" (list (cons 'scope (if (= scope "Model") "model" "handles")) (cons 'handles handles)))
  (pl:db-put "LAST_COUNT" rows) rows)

(defun pl:export-work (/ rows path file row p result)
  (setq rows (pl:count-work))
  (if rows
    (if (setq path (getfiled "保存当前树木统计CSV（Windows ANSI）" "植物数量.csv" "csv" 1))
      (progn
        (setq file (open path "w"))
        (if (not file) (pl:fail "无法写入CSV，请检查路径和文件占用。"))
        (setq result (vl-catch-all-apply 'pl:write-csv (list file rows)))
        (close file)
        (if (vl-catch-all-error-p result)
          (pl:fail (vl-catch-all-error-message result))
          (princ (strcat "\n已导出：" path)))))))

(defun pl:write-csv (file rows / row p)
  (write-line "规格编号,植物名称,胸径cm,地径cm,高度cm,冠幅cm,数量,单位" file)
  (foreach row rows
    (setq p (cadr row))
    (write-line (strcat (pl:csv-cell (pl:get 'spec_no p)) "," (pl:csv-cell (pl:get 'name p)) ","
      (pl:dimension-text 'dbh p) "," (pl:dimension-text 'caliper p) ","
      (pl:dimension-text 'height p) "," (pl:dimension-text 'crown p) ","
      (pl:quantity-text p (caddr row)) "," (pl:csv-cell (pl:get 'quantity_unit p))) file)))

(defun pl:table-work () (pl:count-all-work))
(defun pl:legacy-table-work (/ rows point height table row col i p values)
  (pl:init-layers)
  (if (not (pl:layer-open "PL_表格_苗木")) (pl:fail "表格图层已锁定，请先解锁。"))
  (setq rows (pl:count-work))
  (if (and rows (pl:require-units))
    (progn
      (initget 6)
      (setq height (getreal (strcat "\n表格字高 / cm <"
                    (pl:num (/ (* (pl:paper-height 2.5 (pl:get 'scale (pl:db-get "PLOT_OPTIONS" '((scale . 100.0)))) (pl:units)) 100.0) (pl:units))) ">：")))
      (if height (setq height (* (/ height 100.0) (pl:units)))
        (setq height (pl:paper-height 2.5 (pl:get 'scale (pl:db-get "PLOT_OPTIONS" '((scale . 100.0)))) (pl:units))))
      (if (setq point (getpoint "\n苗木数量表插入点："))
        (progn
          (setq table (vla-AddTable (pl:space) (vlax-3d-point (trans point 1 0))
                         (+ 2 (length rows)) 8 (* 2 height) (* 12 height)))
          (vla-put-Layer table "PL_表格_苗木")
          (vla-SetTextHeight table 7 height)
          (vla-SetTextStyle table 7 (getvar "TEXTSTYLE"))
          (vla-SetText table 0 0 "苗木数量表（记录统计范围）")
          (setq col 0)
          (foreach row '("规格编号" "植物名称" "胸径 cm" "地径 cm" "高度 cm" "冠幅 cm" "数量" "单位")
            (vla-SetText table 1 col row) (setq col (1+ col)))
          (setq i 2)
          (foreach row rows
            (setq p (cadr row) col 0)
            (setq values (list (pl:get 'spec_no p) (pl:get 'name p) (pl:dimension-text 'dbh p) (pl:dimension-text 'caliper p)
                          (pl:dimension-text 'height p) (pl:dimension-text 'crown p)
                          (pl:num (caddr row)) (pl:get 'quantity_unit p)))
            (foreach p values (vla-SetText table i col p) (setq col (1+ col)))
            (setq i (1+ i)))
          (pl:mark (vlax-vla-object->ename table) "TABLE" nil)
          (pl:data-put (vlax-vla-object->ename table) "TABLE_SCOPE" (pl:db-get "LAST_COUNT_SCOPE" nil))
          (princ "\n数量表已记录统计范围。AI微调会更新受管理的表格；其他操作后可重新统计生成。"))))))

(defun pl:info-work (/ e p area)
  (if (setq e (car (entsel "\n点选植物、面积边界或面积标注：")))
    (cond
      ((setq area (pl:area-from-selection e))
        (alert (strcat "区域编号：" (pl:area-number area) "\n植物：" (pl:area-title area)
          "\n面积：" (pl:area-text (pl:area-value area)) " 平方米"
          (if (equal (pl:data-get area "AREA_REPAIRED") 1) "\n闭合方式：推定补线，请核对边界。" "\n闭合方式：原有闭合边界。")
          (if (equal (pl:data-get area "AREA_FITTED") 1) "\n曲线接缝：在面积误差上限内局部拟合，原始边线保留。" ""))))
      ((setq p (pl:plant e))
        (alert (strcat "名称：" (pl:get 'name p) "\n" (pl:spec-text p)
                      "\n显示系数：" (pl:num (pl:get 'factor p))
                      "\n规格编号：" (pl:get 'spec_no p) "\n内部ID：" (pl:get 'id p))))
      (T (alert "该对象没有本插件的植物或面积信息。")))))

(defun c:PLANTCADINIT () (pl:run 'pl:init-layers))
(defun c:PLANTCADSET () (pl:run 'pl:settings-work))
(defun c:PLANTCADPLANT () (pl:run 'pl:library-work))
(defun c:PLANTCADINSERT () (pl:run 'pl:insert-work))
(defun c:PLANTCADUPDATE () (pl:run 'pl:update-work))
(defun c:PLANTCADSIZE () (pl:run 'pl:size-work))
(defun c:PLANTCADSTYLE () (pl:run 'pl:style-work))
(defun c:PLANTCADLABEL () (pl:run 'pl:label-work))
(defun c:PLANTCADSYNC () (pl:run 'pl:sync-drawing))
(defun c:PLANTCADRENAME () (pl:run 'pl:rename-work))
(defun c:PLANTCADCOUNT () (pl:run 'pl:count-work))
(defun c:PLANTCADEXPORT () (pl:run 'pl:export-work))
(defun c:PLANTCADTABLE () (pl:run 'pl:table-work))
(defun c:PLANTCADINFO () (pl:run 'pl:info-work))
(defun c:PLANTCADHELP ()
  (alert (strcat "CountingTrees（数树） III\n双击植物小圆标展开，双击浮窗标题收起。\n"
    "选植物：选择树种，尺寸可沿用上次记录；草类可只保存种类。\n"
    "项目规格：名称/编号检索、分类排列；双击规格行编辑。\n"
    "图中植物：双击或使用编辑菜单，尺寸变化分配独立规格编号。\n"
    "几何面积：框选已有线，自动恢复断口、计算全部区域并标注，再按需关联植物。\n"
    "设置：按已知长度校准单位；保存项目到当前DWG。\n"
    "快捷键：默认仅使用PLANTCAD完整命令，不绑定键盘组合。\n"
    "Ctrl+S保存、Ctrl+Z撤销保持CAD原生行为。\n"
    "手动命令：PLANTCADDESIGN、PLANTCADSET、PLANTCADSHRUB、PLANTCADHELP。")) (princ))

;;; Register a short alias only when no other add-on owns it.
(pl:register-command "PLINIT" "PLANTCADINIT")
(pl:register-command "PLSET" "PLANTCADSET")
(pl:register-command "PLPLANT" "PLANTCADPLANT")
(pl:register-command "PLINSERT" "PLANTCADINSERT")
(pl:register-command "PLUPDATE" "PLANTCADUPDATE")
(pl:register-command "PLSIZE" "PLANTCADSIZE")
(pl:register-command "PLSTYLE" "PLANTCADSTYLE")
(pl:register-command "PLLABEL" "PLANTCADLABEL")
(pl:register-command "PLSYNC" "PLANTCADSYNC")
(pl:register-command "PLRENAME" "PLANTCADRENAME")
(pl:register-command "PLCOUNT" "PLANTCADCOUNT")
(pl:register-command "PLEXPORT" "PLANTCADEXPORT")
(pl:register-command "PLTABLE" "PLANTCADTABLE")
(pl:register-command "PLINFO" "PLANTCADINFO")
(pl:register-command "PLHELP" "PLANTCADHELP")

(if (pl:locate-core)
  (progn
    (pl:run 'pl:init-layers)
    (pl:run 'pl:migrate-defs)
    (princ "\nCountingTrees（数树） 0.3 已加载，植物及出图图层已检查。从CountingTrees（数树）浮窗选品种；输入PLANTCADHELP查看命令。")))
(princ)

