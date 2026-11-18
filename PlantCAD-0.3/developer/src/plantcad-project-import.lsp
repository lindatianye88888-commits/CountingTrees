;;; Collect project plants from existing drawing objects. No geometry is rebuilt.
(defun pl:project-source (e / source role)
  (setq role (pl:role e))
  (cond ((or (pl:plant e) (member role '("AREA" "PROJECT_SOURCE"))) e)
    ((and (member role '("LABEL" "LEADER" "AREA_LABEL" "AREA_LEADER" "AREA_ARROW" "AREA_FILL"))
      (setq source (pl:source e))
      (or (pl:plant source) (equal (pl:role source) "AREA"))) source)
    ((null role) e) (T nil)))

(defun pl:project-source-plant (e / p)
  (if (setq p (pl:data-get e "PROJECT_PLANT"))
    (if (pl:by-id (pl:get 'id p)) (pl:by-id (pl:get 'id p)) p)))
(defun pl:all-project-sources (/ e result)
  (if (assoc 'project-sources pl:*entity-cache*) (cdr (assoc 'project-sources pl:*entity-cache*))
    (progn
      (foreach e (pl:ss-list (ssget "_X" '((-3 ("PLANTCAD01")))))
        (if (equal (pl:role e) "PROJECT_SOURCE") (setq result (cons e result))))
      (reverse result))))

(defun pl:project-canonical (p / existing row key)
  (setq p (pl:upgrade-plant p))
  (setq key (pl:physical-key p) existing (pl:by-id (pl:get 'id p)))
  (if (not (and existing (equal key (pl:physical-key existing))))
    (progn
      (setq existing nil)
      (foreach row (pl:defs)
        (if (equal key (pl:physical-key row)) (setq existing row)))))
  (if existing
    (pl:put 'id (pl:get 'id existing) (pl:put 'spec_no (pl:get 'spec_no existing) p))
    (if (and (/= (pl:get 'id p) "") (/= (pl:get 'spec_no p) "")
      (not (pl:by-id (pl:get 'id p))) (not (pl:spec-error p (pl:used-specs))) (not (pl:history-error p)))
      (progn (pl:save-def p) p) (pl:instance-variant p))))

(defun pl:project-record-matches (record p / good key index value)
  (setq good (and
    (or (= (nth 1 record) "") (equal (pl:normal-name (nth 1 record)) (pl:normal-name (pl:get 'name p))))
    (or (= (nth 2 record) "") (= (strcase (nth 2 record)) (strcase (pl:get 'spec_no p))))
    (or (/= (nth 3 record) 1) (pl:area-kind-p (pl:get 'kind p)))))
  (setq index 5)
  (foreach key '(dbh caliper height crown)
    (setq value (nth index record) index (1+ index))
    (if (and (numberp value) (>= value 0))
      (if (not (equal (pl:get key p) (if (member key '(height crown)) (/ value 100.0) value) 1.0e-6)) (setq good nil)))) good)

(defun pl:project-record-data (record / p species row key index value)
  (setq p (pl:put 'name (nth 1 record) (pl:empty-plant "")))
  (foreach row pl:*project-import-catalog*
    (if (equal (pl:normal-name (pl:get 'name row)) (pl:normal-name (nth 1 record))) (setq species row)))
  (if species (setq p (pl:put 'species_id (pl:get 'id species)
    (pl:put 'kind (pl:species-kind (pl:get 'category species)) p))))
  (if (= (nth 3 record) 1)
    (setq p (pl:put 'quantity_unit "平方米" (pl:put 'kind (if (pl:area-kind-p (pl:get 'kind p)) (pl:get 'kind p) 1) p))))
  (setq index 5)
  (foreach key '(dbh caliper height crown)
    (setq value (nth index record) index (1+ index))
    (if (and (numberp value) (>= value 0))
      (setq p (pl:put key (if (member key '(height crown)) (/ value 100.0) value) p))))
  (if (> (pl:get 'caliper p) 0) (setq p (pl:put 'diameter_mode 1 p))) p)
(defun pl:project-record-seed (record)
  (pl:put 'id (pl:new-id) (pl:put 'spec_no (pl:next-spec-number (pl:used-specs)) (pl:project-record-data record))))

(defun pl:project-record-plant (record / pair matches row p index)
  (if (setq pair (assoc (cdr record) pl:*project-import-memo*)) (cadr pair)
    (progn
      (foreach row (pl:defs)
        (if (pl:project-record-matches record row) (setq matches (append matches (list row)))))
      (cond ((= (length matches) 1) (setq p (car matches)))
        ((> (length matches) 1)
          (setq index (pl:native-value (pl:native-project-match (mapcar 'pl:project-list-row matches) (pl:kind-names))))
          (if (and (numberp index) (>= index 0) (< index (length matches))) (setq p (nth index matches))))
        (T (progn
          (princ (strcat "\n确认采集品种：" (nth 1 record) "。可从“选择植物”选品种；取消则跳过该品种。"))
          (setq p (pl:edit-dialog (pl:project-record-seed record)))
          (if p (setq p (pl:project-canonical p))))))
      (setq pl:*project-import-memo* (cons (list (cdr record) p) pl:*project-import-memo*)) p)))

(defun pl:project-import-one (e / p record role original)
  (setq role (pl:role e) p (pl:annotation-plant e))
  (if (and (equal role "PROJECT_SOURCE") (pl:data-get e "PROJECT_RECORD")
           (boundp 'pl:*native-ui*) pl:*native-ui*)
    (progn
      (setq record (pl:native-project-record (cdr (assoc 5 (entget e)))))
      (if (not record) (setq p nil)
        (if (not (equal record (pl:data-get e "PROJECT_RECORD"))) (setq p nil)))))
  (if (and (pl:writable e) p)
    (progn
      (setq original p p (pl:project-canonical p))
      (if (not (equal original p))
        (pl:data-put e (cond ((= role "TREE") "PLANT") ((= role "AREA") "AREA_PLANT") (T "PROJECT_PLANT")) p)) p)
    (if (and (member role '(nil "PROJECT_SOURCE")) (pl:writable e) (boundp 'pl:*native-ui*) pl:*native-ui*
      (setq record (pl:native-project-record (cdr (assoc 5 (entget e)))))
      (listp record) (= (length record) 9) (= (car record) "PROJECT_RECORD")
      (setq p (pl:project-record-plant record)))
      (progn
        (pl:mark e "PROJECT_SOURCE" nil)
        (pl:data-put e "PROJECT_PLANT" p)
        (pl:data-put e "PROJECT_RECORD" record)
        ;; Text only registers a name. Never use a displayed area/diameter as a count.
        (pl:data-put e "PROJECT_COUNT" (if (and (= (nth 4 record) 1) (/= (nth 3 record) 1)
          (/= (pl:get 'quantity_unit p) "平方米")) 1 nil)) p) nil)))

(defun pl:project-import-tables-open (/ e)
  (foreach e (pl:ss-list (ssget "_X" '((0 . "ACAD_TABLE") (-3 ("PLANTCAD01")))))
    (if (and (equal (pl:role e) "TABLE") (not (pl:writable e)))
      (pl:fail "关联表格图层已锁定，请解锁后再更新已有植物。"))))

(defun pl:collect-project-objects (objects / item e seen n skipped before pl:*project-import-memo* pl:*project-import-catalog*)
  (setq n 0 skipped 0 before (length (pl:defs)) pl:*project-import-catalog* (pl:catalog))
  (if objects
    (progn
      (pl:project-import-tables-open)
      (pl:import-area-label-edits)
      (foreach item objects
        (if (setq e (pl:project-source item))
          (if (not (member e seen))
            (progn
              (setq seen (cons e seen))
              (if (pl:project-import-one e) (setq n (1+ n)) (setq skipped (1+ skipped)))))
          (setq skipped (1+ skipped))))
      (if (> n 0)
        (progn
          (pl:sync-drawing)
          (setq pl:*drawing-changed* nil)
          (if (and (listp pl:*sync-result*) (numberp (cadr pl:*sync-result*)) (> (cadr pl:*sync-result*) 0))
            (princ (strcat "\n有 " (itoa (cadr pl:*sync-result*)) " 个关联表未能更新，请检查图层及命令记录。")))))))
  (princ (strcat "\n采集 " (itoa n) " 个对象；新增 " (itoa (- (length (pl:defs)) before))
    " 个项目规格；取消、锁定或无法识别 " (itoa skipped) " 个。普通文字仅收录名称，数量/面积以关联图形为准。"))
  (list n (- (length (pl:defs)) before) skipped))

(defun pl:collect-project-work (/ selection)
  (princ "\n选择或框选乔木/灌木球图块、植物文字、灌木区域或引出标注，回车确认：")
  (setq selection (ssget "_I"))
  (if (not selection) (setq selection (ssget)))
  (sssetfirst nil nil)
  (pl:collect-project-objects (pl:ss-list selection)))

(defun pl:project-pending-records (objects counts / result seen row e p key)
  (foreach row counts (setq seen (cons (pl:get 'id (cadr row)) seen)))
  (foreach e objects
    (if (and (equal (pl:role e) "PROJECT_SOURCE") (setq p (pl:project-source-plant e)))
      (progn
        (setq key (pl:get 'id p))
        (if (not (member key seen))
          (setq seen (cons key seen) result (append result (list (list p nil "pending")))))))) result)

;;; Clipboard import uses only the objects appended by that paste.
(defun pl:remember-annotation-plant (e p)
  (if (not (equal p (pl:data-get e "ANNOTATION_PLANT"))) (pl:data-put e "ANNOTATION_PLANT" p)))

(defun pl:pasted-plant (raw / pair p)
  (if raw
    (if (setq pair (assoc raw pl:*paste-specs*)) (cdr pair)
      (progn
        (if (not (pl:plant-error raw))
          (progn
            (setq p (pl:upgrade-plant raw))
            (if (and (= (pl:get 'style p) 2) (not (tblsearch "BLOCK" (pl:get 'block p))))
              (setq p (pl:put 'style 0 (pl:put 'block "" (pl:put 'base 1.0 p)))))
            (setq p (pl:project-canonical p))))
        (setq pl:*paste-specs* (cons (cons raw p) pl:*paste-specs*))
        p))))

(defun pl:pasted-plant-key (role)
  (cond ((equal role "TREE") "PLANT")
        ((equal role "AREA") "AREA_PLANT")
        ((equal role "PROJECT_SOURCE") "PROJECT_PLANT")))

(defun pl:pasted-legacy-label (e role / record name kind p)
  (setq record (pl:native-project-record (cdr (assoc 5 (entget e)))))
  (if (and (listp record) (equal (car record) "PROJECT_RECORD")
    (setq name (nth 1 record)) (/= name "") (not (equal (vl-string-search "区域 " name) 0)))
    (progn
      (if (not pl:*project-import-catalog*) (setq pl:*project-import-catalog* (pl:catalog)))
      (setq p (pl:project-record-data record)
        kind (cdr (assoc (cdr (assoc 8 (entget e)))
          '(("PL_标注_树木" . 0) ("PL_灌木_标注" . 1) ("PL_草地_标注" . 2)
            ("PL_灌木球_标注" . 3) ("PL_花境_标注" . 4) ("PL_竹类_标注" . 6)))))
      (if (and (equal kind 2) (= (pl:get 'kind p) 5)) (setq kind 5))
      (if (numberp kind) (setq p (pl:put 'kind kind p)))
      (if (equal role "AREA_LABEL")
        (setq p (pl:put 'quantity_unit "平方米"
          (pl:put 'kind (if (pl:area-kind-p (pl:get 'kind p)) (pl:get 'kind p) 1) p))))
      p)))

(defun pl:pasted-block-number (e no / child ed)
  ;; Preserve the pasted block transform, attribute placement and visibility.
  (if (equal (cdr (assoc 66 (entget e))) 1)
    (progn
      (setq child (entnext e))
      (while (and child (= (cdr (assoc 0 (setq ed (entget child)))) "ATTRIB"))
        (if (and (equal (strcase (cdr (assoc 2 ed))) "PL_SPEC") (not (equal (cdr (assoc 1 ed)) no)))
          (if (entmod (pl:set-dxf 1 no ed)) (entupd e)))
        (setq child (entnext child))))))

(defun pl:pasted-label-number (e p / opts ed text)
  (if (and (setq opts (pl:data-get e "OPTIONS")) (= (pl:get 'mode opts) 3))
    (progn
      (setq ed (entget e) text (strcat "\\qc;" (pl:label-text p opts)))
      (if (not (equal text (cdr (assoc 1 ed))))
        (if (entmod (pl:set-dxf 1 text ed)) (entupd e))))))

(defun pl:pasted-root (e role key / raw p)
  (setq raw (pl:data-get e key) p (pl:pasted-plant raw))
  (cond
    (p
      (if (not (equal p raw)) (pl:data-put e key p))
      (if (and (equal role "TREE") (not (equal (pl:get 'spec_no p) (pl:get 'spec_no raw))))
        (pl:pasted-block-number e (pl:get 'spec_no p)))
      1)
    ((and (equal role "AREA") (not raw)) 0)))

(defun pl:pasted-output (e role roots / source source-role key p raw label)
  (setq source (pl:source e) label (member role '("LABEL" "AREA_LABEL" "AREA_FILL")))
  (if (and (member source roots) (setq source-role (pl:role source))
    (if (member role '("LABEL" "LEADER")) (equal source-role "TREE") (equal source-role "AREA")))
    (progn
      (if (and label (setq key (pl:pasted-plant-key source-role)))
        (progn
          (setq p (pl:data-get source key))
          (pl:remember-annotation-plant e p)
          (if (and p (equal role "LABEL")) (pl:pasted-label-number e p))))
      (if (equal role "AREA_FILL")
        (setq pl:*paste-fills* (cons (cons source (cdr (assoc 5 (entget e)))) pl:*paste-fills*)))
      (if (and (equal role "AREA_LABEL") (equal (cdr (assoc 0 (entget e))) "MTEXT")
        (not (pl:data-get e "OUTPUT_OPTIONS")))
        (setq pl:*paste-anchors* (cons (cons source (cdr (assoc 10 (entget e)))) pl:*paste-anchors*)))
      0)
    ;; A 1005 reference is only trusted if its source was pasted in this batch.
    (progn
      (if label
        (progn
          (setq raw (pl:data-get e "ANNOTATION_PLANT"))
          (if (and (not raw) (member role '("LABEL" "AREA_LABEL")))
            (setq raw (pl:pasted-legacy-label e role)))
          (setq p (pl:pasted-plant raw))))
      (if p
        (progn
          (pl:data-put e "PROJECT_PLANT" p)
          (pl:data-put e "PROJECT_COUNT" nil)
          (pl:mark e "PROJECT_SOURCE" nil)
          (if (equal role "LABEL") (pl:pasted-label-number e p))
          1)
        (progn (pl:mark e nil nil) (if (not label) 0))))))

(defun pl:pasted-object (e roots / role key)
  (if (pl:writable e)
    (if (setq key (pl:pasted-plant-key (setq role (pl:role e))))
      (pl:pasted-root e role key)
      (pl:pasted-output e role roots))))

(defun pl:restore-pasted-area-links (e / fill anchor)
  (setq fill (cdr (assoc e pl:*paste-fills*)) anchor (cdr (assoc e pl:*paste-anchors*)))
  (if (not (equal fill (pl:data-get e "FILL_HANDLE"))) (pl:data-put e "FILL_HANDLE" fill))
  (if (not (equal anchor (pl:data-get e "AREA_ANCHOR"))) (pl:data-put e "AREA_ANCHOR" anchor)))

(defun pl:paste-project-batch (handles / h e role roots outputs areas result n skipped pl:*paste-fills* pl:*paste-anchors*)
  (setq n 0 skipped 0)
  (foreach h handles
    (if (and (setq e (handent h)) (entget e) (setq role (pl:role e)))
      (if (pl:pasted-plant-key role)
        (progn (setq roots (cons e roots)) (if (equal role "AREA") (setq areas (cons e areas))))
        (setq outputs (cons e outputs)))))
  (foreach e (append (reverse roots) (reverse outputs))
    (setq pl:*failure* nil result (vl-catch-all-apply 'pl:pasted-object (list e roots)))
    (if (numberp result) (setq n (+ n result)) (setq skipped (1+ skipped))))
  (foreach e areas
    (if (pl:writable e)
      (if (vl-catch-all-error-p (vl-catch-all-apply 'pl:restore-pasted-area-links (list e)))
        (setq skipped (1+ skipped)))))
  (list n skipped))

(defun pl:import-pasted-work (/ batch result before n skipped tables pl:*paste-specs* pl:*project-import-catalog*
    pl:*sync-busy* pl:*entity-cache* pl:*link-cache* pl:*area-value-cache* pl:*count-cache*)
  (setq before (length (pl:defs)) n 0 skipped 0)
  (foreach batch pl:*paste-batches*
    (setq result (pl:paste-project-batch batch) n (+ n (car result)) skipped (+ skipped (cadr result))))
  ;; Refresh schedules without importing old table edits or rebuilding drawing geometry.
  (if (> n 0)
    (progn
      (setq pl:*sync-busy* T)
      (pl:cache-entities)
      (setq tables (pl:ai-refresh-tables))
      (princ (strcat "\n数树识别到 " (itoa n) " 个粘贴的植物对象，新增 " (itoa (- (length (pl:defs)) before)) " 个项目规格。"))
      (if (> (cadr tables) 0) (princ (strcat "\n有 " (itoa (cadr tables)) " 张关联表未刷新。")))))
  (if (> skipped 0) (princ (strcat "\n有 " (itoa skipped) " 个粘贴对象缺少可用数据或无法写入，未完成识别。")))
  (setq pl:*drawing-changed* nil pl:*failure* nil))

(defun pl:import-pasted-batches (pl:*paste-batches* / pl:*native-ui*)
  (setq pl:*native-ui* T)
  (pl:run 'pl:import-pasted-work))

;;; Delete exactly one project specification, including its managed drawing output.
(defun pl:project-without-id (rows id / result row)
  (foreach row rows
    (if (/= (pl:get 'id row) id) (setq result (append result (list row))))) result)
(defun pl:project-delete-plan (id objects / roots followers tables e p role rows row matches others)
  (foreach e objects
    (setq role (pl:role e) p nil)
    (cond ((= role "TREE") (setq p (pl:data-get e "PLANT")))
      ((= role "AREA") (setq p (pl:data-get e "AREA_PLANT")))
      ((= role "PROJECT_SOURCE") (setq p (pl:data-get e "PROJECT_PLANT"))))
    (if (and p (= (pl:get 'id p) id)) (setq roots (cons e roots))))
  (foreach e objects
    (setq role (pl:role e))
    (if (and (member role '("LABEL" "LEADER" "AREA_LABEL" "AREA_LEADER" "AREA_ARROW" "AREA_FILL" "FILL_EDGE"))
      (member (pl:source e) roots)) (setq followers (cons e followers)))
    (if (= role "TABLE")
      (progn
        (setq rows (pl:data-get e "TABLE_ROWS") matches nil others nil)
        (foreach row rows (if (= (car row) id) (setq matches T) (setq others T)))
        (if matches
          (progn
            (if (not (pl:writable e)) (pl:fail "关联表格图层已锁定，请解锁后再删除规格。"))
            (if (not others) (setq tables (cons e tables))))))))
  (foreach e (append roots followers)
    (if (not (pl:writable e)) (pl:fail "待删除植物、标注或填充的图层已锁定，请先解锁。")))
  (list roots followers tables))
(defun pl:delete-project-spec (p / id plan handles e result remaining)
  (if (not (and (boundp 'pl:*native-ui*) pl:*native-ui*))
    (pl:fail "删除规格需要加载完整原生插件；当前没有删除任何内容。"))
  (setq id (pl:get 'id p)
    plan (pl:project-delete-plan id (pl:ss-list (ssget "_X" '((-3 ("PLANTCAD01")))))))
  (setq result (pl:native-value (pl:native-project-delete-confirm
    (strcat (pl:get 'spec_no p) " " (pl:get 'name p))
    (+ (length (car plan)) (length (cadr plan))) (length (caddr plan)))))
  (if (not (numberp result)) (pl:fail (if (= (type result) 'STR) result "删除确认失败，未作更改。")))
  (if (= result 1)
    (progn
      (foreach e (append (car plan) (cadr plan) (caddr plan))
        (setq handles (cons (cdr (assoc 5 (entget e))) handles)))
      (if handles
        (progn
          (setq result (pl:native-value (pl:native-project-erase handles)))
          (if (not (and (numberp result) (= result (length handles))))
            (pl:fail (if (= (type result) 'STR) result "删除对象失败，项目规格尚未移除。")))))
      (setq remaining (pl:project-without-id (pl:defs) id))
      (pl:db-put "PLANTS" remaining)
      (pl:db-put "SPEC_HISTORY" (pl:project-without-id (pl:db-get "SPEC_HISTORY" nil) id))
      (if (= (pl:db-get "CURRENT" "") id)
        (pl:db-put "CURRENT" (if remaining (pl:get 'id (car remaining)) "")))
      (setq pl:*entity-cache* nil pl:*link-cache* nil pl:*count-cache* nil)
      (pl:sync-drawing) (setq pl:*drawing-changed* nil)
      (if (and (listp pl:*sync-result*) (numberp (cadr pl:*sync-result*)) (> (cadr pl:*sync-result*) 0))
        (princ (strcat "\n有 " (itoa (cadr pl:*sync-result*)) " 个关联表未能刷新，请查看命令记录；可用 U 撤销本次改动。")))
      (princ (strcat "\n已删除规格 " (pl:get 'spec_no p) "；对应图上对象已删除，关联表已处理。")) T)
    (progn (princ "\n已取消删除，图纸和项目规格未更改。") nil)))
(setq pl:*paste-import-loaded* T)
(princ)
