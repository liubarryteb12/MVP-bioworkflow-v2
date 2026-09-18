# 统一出图风格 —— 所有 P1 图表模块必须 source 本文件后作图。
#
# 依据（唯一真源）：
#   02版《合集-全五份》P1 §11.2 产出规格：
#     分析图 矢量 PDF + SVG + PNG + TIFF + JPG 五格式；宽度 85 / 160 mm
#   P1 §11.3 出图时遵守：
#     字体 Arial / Helvetica 7–8 pt；线宽 0.25–1 pt；色盲友好、避免红绿；
#     图内无图题、无图注、无网格；单文件 ≤10 MB；命名统一
#   参照：第一版/09.SCI文章出图与排版参考/02+03（Elsevier/Nature/BMC/Wiley 通吃配置）
#
# 为什么必须统一：此前各模块各自 pdf(width=7,height=5)（=177.8×127 mm，超双栏版心）、
# 图内写 main= 图题、字体线宽全用默认值——四项全部不符合 §11.3。

# ---------- 字体：取系统真实可用的 Arial 或度量兼容替代 ----------
fig_font <- local({
  cands <- c("Arial", "Liberation Sans", "Helvetica", "Nimbus Sans", "DejaVu Sans")
  fams <- tryCatch(system("fc-list : family", intern = TRUE), error = function(e) character(0))
  if (length(fams)) {
    fams <- unique(trimws(unlist(strsplit(paste(fams, collapse = ","), ","))))
    for (c in cands) {
      if (any(tolower(fams) == tolower(c))) {
        cat("figure font: ", c, "\n", sep = "")
        return(c)
      }
    }
  }
  cat("figure font: sans (未探测到 Arial/Liberation Sans)\n")
  "sans"
})

# ---------- 色盲友好调色板（Okabe-Ito，§11.3 避免红绿对比） ----------
fig_pal <- c(orange = "#E69F00", sky = "#56B4E9", green = "#009E73", yellow = "#F0E442",
             blue = "#0072B2", vermillion = "#D55E00", purple = "#CC79A7", grey = "#999999")

FIG_PT <- 8        # 基准字号：§11.3 要求 7–8 pt
FIG_LWD <- 0.8     # 基准线宽：§11.3 要求 0.25–1 pt

# ---------- 打开画布：宽度按 85（单栏）/ 160（双栏）mm ----------
fig_open <- function(path, width_mm = 85, height_mm = 70) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  w_in <- width_mm / 25.4
  h_in <- height_mm / 25.4
  # cairo_pdf 会嵌入字体（普通 pdf() 对 base14 字体不嵌入，期刊要求嵌入）。
  # R 若未编入 cairo，则回退到 pdf()，并如实提示字体可能未嵌入。
  ok <- tryCatch({
    grDevices::cairo_pdf(path, width = w_in, height = h_in,
                         family = fig_font, pointsize = FIG_PT, bg = "white", onefile = TRUE)
    TRUE
  }, error = function(e) FALSE)
  if (!ok) {
    cat("figure device: cairo_pdf unavailable, fallback to pdf()\n")
    grDevices::pdf(path, width = w_in, height = h_in,
                   family = fig_font, pointsize = FIG_PT, bg = "white", onefile = TRUE)
  }
  graphics::par(mar = c(4.0, 4.3, 0.8, 0.9), mgp = c(1.9, 0.55, 0), tcl = -0.25,
                las = 1, lwd = FIG_LWD, xpd = FALSE, bty = "l",
                cex.axis = 0.9, cex.lab = 1.0, family = fig_font)
}

fig_close <- function() {
  while (grDevices::dev.cur() > 1) grDevices::dev.off()
}

# ---------- 轴标签规范：物理量 (单位)、句首大写 ----------
fig_axis <- function(...) graphics::title(...)
