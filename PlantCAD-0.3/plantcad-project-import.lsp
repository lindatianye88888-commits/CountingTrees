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

(defun pl:project-canonical (p / existing row)
  (setq p (pl:upgrade-plant p))
  (foreach row (pl:defs)
    (if (equal (pl:physical-key row) (pl:physical-key p)) (setq existing row)))
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

(defun pl:project-record-seed (record / p species row key index value)
  (setq p (pl:empty-plant (pl:new-id)))
  (setq p (pl:put 'spec_no (pl:next-spec-number (pl:used-specs)) (pl:put 'name (nth 1 record) p)))
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
  (if (and (equal role "PROJECT_SOURCE") (boundp 'pl:*native-ui*) pl:*native-ui*)
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
(princ)
