pl_area_output : dialog {
 label = "种植面积出图标注";
 : popup_list { key = "area_layout"; label = "引线标注样式"; edit_width = 46; }
 : toggle { key = "area_fill"; label = "同时按区域关联植物自动填充"; }
 : toggle { key = "area_bind"; label = "多块区域默认沿用上一次选择的品种（仍可逐块更改）"; }
 : text { label = "按当前出图比例和纸面字高生成；引线、植物名称及面积保持关联。"; }
 : text { label = "第一点定折点，第二点定横线尾端及左右方向，最后选择或输入品种。"; }
 : text { label = "回车跳过当前区域；横线过短时文字等比缩小以放入横线范围。"; }
 ok_cancel;
}
pl_area_species : dialog {
 label = "灌木引出标注 - 选择或输入品种";
 : text { label = "折点和横线尾端已确定。选择项目中的具体规格，或直接输入新植物名称。"; }
 : row {
  : edit_box { key = "area_query"; label = "检索名称/编号"; edit_width = 35; }
  : button { key = "area_search"; label = "检索"; }
  : button { key = "area_add"; label = "从品种库添加"; }
 }
 : list_box { key = "area_columns"; width = 114; height = 2; fixed_width_font = true; tabs = "18 30 54 66 78 90 102"; }
 : list_box { key = "area_plants"; width = 114; height = 10; fixed_width_font = true; tabs = "18 30 54 66 78 90 102"; }
 : edit_box { key = "area_name"; label = "植物名称/规格编号"; edit_width = 45; }
 : text { label = "同名不同规格请从列表选定；新名称按面积植物建立，可随后补全项目规格。"; }
 ok_cancel;
}
pl_library : dialog {
 label = "CountingTrees（数树） - 项目植物与规格";
 : text { label = "按分类排列，可按名称或编号检索；不同尺寸使用独立规格编号。"; }
 : row {
  : popup_list { key = "project_kind"; label = "分类"; edit_width = 18; }
  : edit_box { key = "project_query"; label = "名称/编号检索"; edit_width = 24; }
  : button { key = "project_filter"; label = "检索"; }
 }
 : list_box { key = "project_columns"; width = 114; height = 2; fixed_width_font = true; tabs = "18 30 54 66 78 90 102"; }
 : list_box { key = "plants"; width = 114; height = 13; fixed_width_font = true; tabs = "18 30 54 66 78 90 102"; allow_accept = true; }
 : row {
  : button { key = "add"; label = "从品种库建规格"; }
  : button { key = "manual"; label = "手动新增"; }
  : button { key = "clone"; label = "复制新规格"; }
  : button { key = "edit"; label = "修改规格"; is_default = true; }
  : button { key = "update"; label = "更新已有植物"; }
  : button { key = "delete"; label = "删除规格"; }
 }
 : text { label = "修改项目规格会同步图中对象及所有关联表；双击单株只修改该株。"; }
 : row {
  : button { key = "place"; label = "设为当前并开始布置"; }
  : button { key = "accept"; label = "设为当前规格"; }
  : button { key = "cancel"; label = "关闭"; is_cancel = true; }
 }
}
pl_edit : dialog {
 label = "植物规格与图例";
 : text { key = "plant_identity"; width = 76; }
 : popup_list { key = "plant_choice"; label = "选择植物（全部植物）"; edit_width = 38; }
 : edit_box { key = "name"; label = "植物名称（可修改）"; edit_width = 30; }
 : row {
  : edit_box { key = "spec_no"; label = "规格编号"; edit_width = 18; }
  : popup_list { key = "quantity_unit"; label = "计数单位"; edit_width = 8; }
 }
 : popup_list { key = "kind"; label = "类别"; edit_width = 25; }
 : boxed_column {
  label = "苗木规格 · 单位统一为cm";
  : edit_box { key = "crown"; label = "冠幅 / cm"; edit_width = 18; }
  : edit_box { key = "height"; label = "高度 / cm"; edit_width = 18; }
  : edit_box { key = "dbh"; label = "胸径 / cm（可填——）"; edit_width = 18; }
  : edit_box { key = "caliper"; label = "地径 / cm（可填——）"; edit_width = 18; }
  : text { label = "先确认冠幅和高度；胸径、地径可只填一个，也可暂留空。"; }
  : text { label = "新植物带入可修改的设计初值；同品种优先沿用上次尺寸。草类可全留空。"; }
  : popup_list { key = "diameter_mode"; label = "树名下方显示"; edit_width = 24; }
 }
 : boxed_row {
  label = "平面图例 · 选择后点击操作面板的“开始布置”";
  : column {
   : image { key = "symbol_preview"; width = 24; height = 6; color = -2; }
   : text { key = "preview_caption"; width = 30; }
  }
  : column {
   : popup_list { key = "style"; label = "图例样式"; edit_width = 24; }
   : edit_box { key = "factor"; label = "显示系数（1=实际冠幅）"; edit_width = 10; }
   : edit_box { key = "block"; label = "自定义普通图块名"; edit_width = 24; }
   : edit_box { key = "base"; label = "自定义图块基准外径 / cm"; edit_width = 10; }
  }
 }
 : boxed_column {
  label = "灌木、地被、花境与草坪填充";
  : popup_list { key = "fill_pattern"; label = "填充图案（允许重复）"; edit_width = 30; }
  : row {
   : edit_box { key = "fill_scale"; label = "填充比例 / cm"; edit_width = 8; }
   : edit_box { key = "fill_angle"; label = "角度 / 度"; edit_width = 8; }
  }
 }
 : text { label = "灌木球按单株布置；灌木、地被、花境、草坪可按区域填充。"; }
 : text { key = "error"; width = 78; height = 2; }
 : row {
  : button { key = "accept"; label = "保存规格"; is_default = true; }
  : button { key = "cancel"; label = "取消"; is_cancel = true; }
 }
}
pl_settings : dialog {
 label = "绘图单位与出图文字";
 : text { key = "unit_hint"; width = 74; }
 : popup_list { key = "unit"; label = "模型绘图单位"; edit_width = 25; }
 : text { label = "未知或混合比例底图，请从设置菜单使用“按已知长度校准单位”。"; }
 : edit_box { key = "plot_scale"; label = "出图比例 1 :"; edit_width = 15; }
 : edit_box { key = "paper_height"; label = "纸面字高 / cm"; edit_width = 15; }
 : toggle { key = "show_number"; label = "图例同时显示规格编号（默认关闭）"; }
 : text { label = "默认纸面字高1cm；按出图比例换算模型文字。"; }
 : text { label = "在布局纸空间直接布置时按1:1计算；不同视口比例请另建视图。"; }
 : text { label = "单位、比例和字高同步用于已有乔木文字、灌木引线及面积指标。"; }
 : text { label = "文字较长时自动延长引线横线；模型冠幅和已计算面积保持原值。"; }
 : text { key = "error"; width = 72; }
 ok_cancel;
}
pl_label : dialog {
 label = "外置植物名称与规格标注";
 : popup_list { key = "mode"; label = "标注内容"; edit_width = 36; }
 : popup_list { key = "prefix"; label = "径值下行格式"; edit_width = 36; }
 : toggle { key = "units"; label = "径值下行附加 cm"; }
 : edit_box { key = "height"; label = "文字高度 / cm"; edit_width = 15; }
 : toggle { key = "leader"; label = "绘制从植物中心到标注点的引线"; }
 : text { label = "径值按该规格所选的胸径或地径；未填写时不显示下行占位符。"; }
 : text { label = "外置标注保持手动位置与字高；图块内部的文字在设置菜单中调整。"; }
 : text { key = "error"; width = 65; }
 ok_cancel;
}
pl_catalog : dialog {
 label = "CountingTrees（数树） - 可编辑植物品种表";
 : row {
  : popup_list { key = "category"; label = "形态"; edit_width = 22; }
  : edit_box { key = "region"; label = "地区关键词"; edit_width = 10; }
  : edit_box { key = "query"; label = "名称搜索"; edit_width = 15; }
  : button { key = "filter"; label = "筛选"; }
 }
 : row {
  : boxed_column {
   label = "植物库 · 点击选择，可按Ctrl/Shift多选";
   : list_box { key = "species"; width = 54; height = 16; multiple_select = true; }
  }
  : boxed_column {
   label = "已经选中的植物";
   : text { key = "chosen_count"; width = 32; }
   : list_box { key = "chosen_species"; width = 34; height = 14; }
   : row {
    : button { key = "remove_chosen"; label = "移除选中"; }
    : button { key = "clear_chosen"; label = "清空已选"; }
   }
  }
 }
 : text { key = "detail"; width = 88; }
 : text { label = "常绿/落叶来自分类；彩叶/开花可在品种资料中勾选。切换筛选保留右侧清单。"; }
 : row {
  : button { key = "add"; label = "增补品种"; }
  : button { key = "edit"; label = "修改选中品种"; }
  : button { key = "export"; label = "导出共享品种表"; }
  : button { key = "import"; label = "导入共享品种表"; }
 }
 : text { key = "error"; width = 88; }
 : row {
  : button { key = "accept"; label = "为右侧已选植物建立规格"; is_default = true; }
  : button { key = "cancel"; label = "关闭"; is_cancel = true; }
 }
}
pl_species : dialog {
 label = "编辑植物品种";
 : text { key = "identity"; width = 70; }
 : edit_box { key = "name"; label = "品种名称"; edit_width = 30; }
 : popup_list { key = "category"; label = "形态分类"; edit_width = 24; }
 : boxed_row {
  label = "植物标签（按已核实资料勾选，可多选）";
  : toggle { key = "evergreen"; label = "常绿"; }
  : toggle { key = "deciduous"; label = "落叶"; }
  : toggle { key = "color_leaf"; label = "彩叶"; }
  : toggle { key = "flowering"; label = "开花"; }
 }
 : edit_box { key = "region"; label = "参考/适用地区"; edit_width = 38; }
 : edit_box { key = "supply"; label = "供应情况/询价记录"; edit_width = 38; }
 : edit_box { key = "source"; label = "资料来源或网址"; edit_width = 55; }
 : edit_box { key = "note"; label = "备注（品种/适生/采购条件）"; edit_width = 55; }
 : text { key = "error"; width = 75; }
 ok_cancel;
}
