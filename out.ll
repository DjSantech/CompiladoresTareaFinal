declare i32 @printf(i8*, ...)
declare i8* @malloc(i32)

@.fmt_int   = private unnamed_addr constant [4 x i8] c"%d\0A\00"
@.fmt_float = private unnamed_addr constant [4 x i8] c"%f\0A\00"
@.fmt_char  = private unnamed_addr constant [4 x i8] c"%c\0A\00"
@.fmt_str   = private unnamed_addr constant [4 x i8] c"%s\0A\00"
@.len.print_board.p0 = global i32 0
@.len.knight_tour_warnsdorff.p0 = global i32 0
@.str.c71474 = private unnamed_addr constant [42 x i8] [i8 78, i8 111, i8 32, i8 115, i8 101, i8 32, i8 112, i8 117, i8 100, i8 111, i8 32, i8 99, i8 111, i8 109, i8 112, i8 108, i8 101, i8 116, i8 97, i8 114, i8 32, i8 101, i8 108, i8 32, i8 116, i8 111, i8 117, i8 114, i8 32, i8 100, i8 101, i8 115, i8 100, i8 101, i8 32, i8 40, i8 48, i8 44, i8 48, i8 41, i8 10, i8 0]
@.str.7278d4 = private unnamed_addr constant [27 x i8] [i8 84, i8 111, i8 117, i8 114, i8 32, i8 99, i8 111, i8 109, i8 112, i8 108, i8 101, i8 116, i8 111, i8 32, i8 101, i8 110, i8 99, i8 111, i8 110, i8 116, i8 114, i8 97, i8 100, i8 111, i8 58, i8 10, i8 0]
@.str.914d62 = private unnamed_addr constant [2 x i8] [i8 10, i8 0]
@.str.6dc465 = private unnamed_addr constant [2 x i8] [i8 32, i8 0]

@N = global i32 8
@KNIGHT_DX = global [8 x i32] [i32 2, i32 1, i32 -1, i32 -2, i32 -2, i32 -1, i32 1, i32 2]
@KNIGHT_DY = global [8 x i32] [i32 1, i32 2, i32 2, i32 1, i32 -1, i32 -2, i32 -2, i32 -1]
define i32 @index_of(i32 %x, i32 %y) {
  %t1 = alloca i32
  store i32 %x, i32* %t1
  %t2 = alloca i32
  store i32 %y, i32* %t2
  %t3 = load i32, i32* %t2
  %t4 = load i32, i32* @N
  %t5 = mul i32 %t3, %t4
  %t6 = load i32, i32* %t1
  %t7 = add i32 %t5, %t6
  ret i32 %t7
endfn.1:
  ret i32 0
}

define i1 @in_board(i32 %x, i32 %y) {
  %t8 = alloca i32
  store i32 %x, i32* %t8
  %t9 = alloca i32
  store i32 %y, i32* %t9
  %t10 = load i32, i32* %t8
  %t11 = icmp slt i32 %t10, 0
  %t12 = load i32, i32* %t8
  %t13 = load i32, i32* @N
  %t14 = icmp sge i32 %t12, %t13
  %t15 = or i1 %t11, %t14
  br i1 %t15, label %then.3, label %else.4
then.3:
  ret i1 0
  br label %endif.5
else.4:
  br label %endif.5
endif.5:
  %t16 = load i32, i32* %t9
  %t17 = icmp slt i32 %t16, 0
  %t18 = load i32, i32* %t9
  %t19 = load i32, i32* @N
  %t20 = icmp sge i32 %t18, %t19
  %t21 = or i1 %t17, %t20
  br i1 %t21, label %then.6, label %else.7
then.6:
  ret i1 0
  br label %endif.8
else.7:
  br label %endif.8
endif.8:
  ret i1 1
endfn.2:
  ret i1 0
}

define i1 @is_valid_move(i32 %x, i32 %y, i32* %board) {
  %t22 = alloca i32
  store i32 %x, i32* %t22
  %t23 = alloca i32
  store i32 %y, i32* %t23
  %t24 = alloca i32*
  store i32* %board, i32** %t24
  %t25 = alloca i32
  store i32 0, i32* %t25
  %t26 = icmp ne i32 0, 0
  br i1 %t26, label %then.10, label %else.11
then.10:
  ret i1 0
  br label %endif.12
else.11:
  br label %endif.12
endif.12:
  %t27 = load i32, i32* %t22
  %t28 = load i32, i32* %t23
  %t29 = call i32 @index_of(i32 %t27, i32 %t28)
  store i32 %t29, i32* %t25
  %t30 = load i32*, i32** %t24
  %t31 = getelementptr inbounds i32, i32* %t30, i32 0
  %t32 = load i32, i32* %t31
  %t33 = icmp ne i32 %t32, 0
  br i1 %t33, label %then.13, label %else.14
then.13:
  ret i1 0
  br label %endif.15
else.14:
  br label %endif.15
endif.15:
  ret i1 1
endfn.9:
  ret i1 0
}

define i32 @degree_of(i32 %x, i32 %y, i32* %board) {
  %t34 = alloca i32
  store i32 %x, i32* %t34
  %t35 = alloca i32
  store i32 %y, i32* %t35
  %t36 = alloca i32*
  store i32* %board, i32** %t36
  %t37 = alloca i32
  store i32 0, i32* %t37
  %t38 = alloca i32
  store i32 0, i32* %t38
  %t39 = alloca i32
  store i32 0, i32* %t39
  %t40 = alloca i32
  store i32 0, i32* %t40
  store i32 0, i32* %t38
  br label %for.head.17
for.head.17:
  %t41 = load i32, i32* %t38
  %t42 = icmp slt i32 %t41, 8
  br i1 %t42, label %for.body.18, label %for.end.20
for.body.18:
  %t43 = load i32, i32* %t34
  %t44 = getelementptr inbounds [8 x i32], [8 x i32]* @KNIGHT_DX, i32 0, i32 0
  %t45 = load i32, i32* %t44
  %t46 = add i32 %t43, %t45
  store i32 %t46, i32* %t39
  %t47 = load i32, i32* %t35
  %t48 = getelementptr inbounds [8 x i32], [8 x i32]* @KNIGHT_DY, i32 0, i32 0
  %t49 = load i32, i32* %t48
  %t50 = add i32 %t47, %t49
  store i32 %t50, i32* %t40
  %t51 = load i32, i32* %t39
  %t52 = load i32, i32* %t40
  %t53 = load i32*, i32** %t36
  %t54 = call i1 @is_valid_move(i32 %t51, i32 %t52, i32* %t53)
  br i1 %t54, label %then.21, label %else.22
then.21:
  %t55 = load i32, i32* %t37
  %t56 = add i32 %t55, 1
  store i32 %t56, i32* %t37
  br label %endif.23
else.22:
  br label %endif.23
endif.23:
  br label %for.step.19
for.step.19:
  %t57 = load i32, i32* %t38
  %t58 = add i32 %t57, 1
  store i32 %t58, i32* %t38
  br label %for.head.17
for.end.20:
  %t59 = load i32, i32* %t37
  ret i32 %t59
endfn.16:
  ret i32 0
}

define i32 @warnsdorff_next(i32 %x, i32 %y, i32* %board) {
  %t60 = alloca i32
  store i32 %x, i32* %t60
  %t61 = alloca i32
  store i32 %y, i32* %t61
  %t62 = alloca i32*
  store i32* %board, i32** %t62
  %t63 = alloca i32
  store i32 0, i32* %t63
  %t64 = alloca i32
  %t65 = sub i32 0, 1
  store i32 %t65, i32* %t64
  %t66 = alloca i32
  store i32 9, i32* %t66
  %t67 = alloca i32
  store i32 0, i32* %t67
  %t68 = alloca i32
  store i32 0, i32* %t68
  %t69 = alloca i32
  store i32 0, i32* %t69
  store i32 0, i32* %t63
  br label %for.head.25
for.head.25:
  %t70 = load i32, i32* %t63
  %t71 = icmp slt i32 %t70, 8
  br i1 %t71, label %for.body.26, label %for.end.28
for.body.26:
  %t72 = load i32, i32* %t60
  %t73 = getelementptr inbounds [8 x i32], [8 x i32]* @KNIGHT_DX, i32 0, i32 0
  %t74 = load i32, i32* %t73
  %t75 = add i32 %t72, %t74
  store i32 %t75, i32* %t67
  %t76 = load i32, i32* %t61
  %t77 = getelementptr inbounds [8 x i32], [8 x i32]* @KNIGHT_DY, i32 0, i32 0
  %t78 = load i32, i32* %t77
  %t79 = add i32 %t76, %t78
  store i32 %t79, i32* %t68
  %t80 = load i32, i32* %t67
  %t81 = load i32, i32* %t68
  %t82 = load i32*, i32** %t62
  %t83 = call i1 @is_valid_move(i32 %t80, i32 %t81, i32* %t82)
  br i1 %t83, label %then.29, label %else.30
then.29:
  %t84 = load i32, i32* %t67
  %t85 = load i32, i32* %t68
  %t86 = load i32*, i32** %t62
  %t87 = call i32 @degree_of(i32 %t84, i32 %t85, i32* %t86)
  store i32 %t87, i32* %t69
  %t88 = load i32, i32* %t69
  %t89 = load i32, i32* %t66
  %t90 = icmp slt i32 %t88, %t89
  br i1 %t90, label %then.32, label %else.33
then.32:
  %t91 = load i32, i32* %t69
  store i32 %t91, i32* %t66
  %t92 = load i32, i32* %t63
  store i32 %t92, i32* %t64
  br label %endif.34
else.33:
  br label %endif.34
endif.34:
  br label %endif.31
else.30:
  br label %endif.31
endif.31:
  br label %for.step.27
for.step.27:
  %t93 = load i32, i32* %t63
  %t94 = add i32 %t93, 1
  store i32 %t94, i32* %t63
  br label %for.head.25
for.end.28:
  %t95 = load i32, i32* %t64
  ret i32 %t95
endfn.24:
  ret i32 0
}

define i32 @knight_step_warnsdorff(i32 %curr_pos, i32* %board) {
  %t96 = alloca i32
  store i32 %curr_pos, i32* %t96
  %t97 = alloca i32*
  store i32* %board, i32** %t97
  %t98 = alloca i32
  store i32 0, i32* %t98
  %t99 = alloca i32
  store i32 0, i32* %t99
  %t100 = alloca i32
  store i32 0, i32* %t100
  %t101 = alloca i32
  store i32 0, i32* %t101
  %t102 = alloca i32
  store i32 0, i32* %t102
  %t103 = load i32, i32* %t96
  %t104 = load i32, i32* @N
  %t105 = srem i32 %t103, %t104
  store i32 %t105, i32* %t98
  %t106 = load i32, i32* %t96
  %t107 = load i32, i32* @N
  %t108 = sdiv i32 %t106, %t107
  store i32 %t108, i32* %t99
  %t109 = load i32, i32* %t98
  %t110 = load i32, i32* %t99
  %t111 = load i32*, i32** %t97
  %t112 = call i32 @warnsdorff_next(i32 %t109, i32 %t110, i32* %t111)
  store i32 %t112, i32* %t100
  %t113 = load i32, i32* %t100
  %t114 = icmp slt i32 %t113, 0
  br i1 %t114, label %then.36, label %else.37
then.36:
  %t115 = sub i32 0, 1
  ret i32 %t115
  br label %endif.38
else.37:
  br label %endif.38
endif.38:
  %t116 = load i32, i32* %t98
  %t117 = getelementptr inbounds [8 x i32], [8 x i32]* @KNIGHT_DX, i32 0, i32 0
  %t118 = load i32, i32* %t117
  %t119 = add i32 %t116, %t118
  store i32 %t119, i32* %t101
  %t120 = load i32, i32* %t99
  %t121 = getelementptr inbounds [8 x i32], [8 x i32]* @KNIGHT_DY, i32 0, i32 0
  %t122 = load i32, i32* %t121
  %t123 = add i32 %t120, %t122
  store i32 %t123, i32* %t102
  %t124 = load i32, i32* %t101
  %t125 = load i32, i32* %t102
  %t126 = call i32 @index_of(i32 %t124, i32 %t125)
  ret i32 %t126
endfn.35:
  ret i32 0
}

define void @print_board(i32* %board) {
  %t127 = alloca i32*
  store i32* %board, i32** %t127
  %t128 = alloca i32
  store i32 0, i32* %t128
  %t129 = alloca i32
  store i32 0, i32* %t129
  %t130 = alloca i32
  store i32 0, i32* %t130
  store i32 0, i32* %t128
  br label %for.head.40
for.head.40:
  %t131 = load i32, i32* %t128
  %t132 = load i32, i32* @N
  %t133 = icmp slt i32 %t131, %t132
  br i1 %t133, label %for.body.41, label %for.end.43
for.body.41:
  store i32 0, i32* %t129
  br label %for.head.44
for.head.44:
  %t134 = load i32, i32* %t129
  %t135 = load i32, i32* @N
  %t136 = icmp slt i32 %t134, %t135
  br i1 %t136, label %for.body.45, label %for.end.47
for.body.45:
  %t137 = load i32, i32* %t129
  %t138 = load i32, i32* %t128
  %t139 = call i32 @index_of(i32 %t137, i32 %t138)
  store i32 %t139, i32* %t130
  %t140 = load i32*, i32** %t127
  %t141 = getelementptr inbounds i32, i32* %t140, i32 0
  %t142 = load i32, i32* %t141
%t143 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_int, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t143, i32 %t142)
  %t144 = getelementptr inbounds [2 x i8], [2 x i8]* @.str.6dc465, i32 0, i32 0
%t145 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t145, i8* %t144)
  br label %for.step.46
for.step.46:
  %t146 = load i32, i32* %t129
  %t147 = add i32 %t146, 1
  store i32 %t147, i32* %t129
  br label %for.head.44
for.end.47:
  %t148 = getelementptr inbounds [2 x i8], [2 x i8]* @.str.914d62, i32 0, i32 0
%t149 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t149, i8* %t148)
  br label %for.step.42
for.step.42:
  %t150 = load i32, i32* %t128
  %t151 = add i32 %t150, 1
  store i32 %t151, i32* %t128
  br label %for.head.40
for.end.43:
endfn.39:
  ret void
}

define i1 @knight_tour_warnsdorff(i32* %board, i32 %start_x, i32 %start_y) {
  %t152 = alloca i32*
  store i32* %board, i32** %t152
  %t153 = alloca i32
  store i32 %start_x, i32* %t153
  %t154 = alloca i32
  store i32 %start_y, i32* %t154
  %t155 = alloca i32
  %t156 = load i32, i32* @N
  %t157 = load i32, i32* @N
  %t158 = mul i32 %t156, %t157
  store i32 %t158, i32* %t155
  %t159 = alloca i32
  store i32 0, i32* %t159
  %t160 = alloca i32
  store i32 0, i32* %t160
  %t161 = alloca i32
  store i32 0, i32* %t161
  store i32 0, i32* %t161
  br label %for.head.49
for.head.49:
  %t162 = load i32, i32* %t161
  %t163 = load i32, i32* %t155
  %t164 = icmp slt i32 %t162, %t163
  br i1 %t164, label %for.body.50, label %for.end.52
for.body.50:
  %t165 = load i32*, i32** %t152
  %t166 = getelementptr inbounds i32, i32* %t165, i32 0
  store i32 0, i32* %t166
  br label %for.step.51
for.step.51:
  %t167 = load i32, i32* %t161
  %t168 = add i32 %t167, 1
  store i32 %t168, i32* %t161
  br label %for.head.49
for.end.52:
  %t169 = load i32, i32* %t153
  %t170 = load i32, i32* %t154
  %t171 = call i32 @index_of(i32 %t169, i32 %t170)
  store i32 %t171, i32* %t159
  %t172 = load i32*, i32** %t152
  %t173 = getelementptr inbounds i32, i32* %t172, i32 0
  store i32 1, i32* %t173
  store i32 2, i32* %t160
  br label %for.head.53
for.head.53:
  %t174 = load i32, i32* %t160
  %t175 = load i32, i32* %t155
  %t176 = icmp sle i32 %t174, %t175
  br i1 %t176, label %for.body.54, label %for.end.56
for.body.54:
  %t177 = load i32, i32* %t159
  %t178 = load i32*, i32** %t152
  %t179 = call i32 @knight_step_warnsdorff(i32 %t177, i32* %t178)
  store i32 %t179, i32* %t159
  %t180 = load i32, i32* %t159
  %t181 = icmp slt i32 %t180, 0
  br i1 %t181, label %then.57, label %else.58
then.57:
  ret i1 0
  br label %endif.59
else.58:
  br label %endif.59
endif.59:
  %t182 = load i32*, i32** %t152
  %t183 = getelementptr inbounds i32, i32* %t182, i32 0
  %t184 = load i32, i32* %t160
  store i32 %t184, i32* %t183
  br label %for.step.55
for.step.55:
  %t185 = load i32, i32* %t160
  %t186 = add i32 %t185, 1
  store i32 %t186, i32* %t160
  br label %for.head.53
for.end.56:
  ret i1 1
endfn.48:
  ret i1 0
}

define i32 @main() {
  %t187 = alloca i32*
  %t188 = mul i32 64, 4
  %t189 = call i8* @malloc(i32 %t188)
  %t190 = bitcast i8* %t189 to i32*
  store i32* %t190, i32** %t187
  %t191 = alloca i32
  store i32 64, i32* %t191
  %t192 = alloca i1
  store i1 0, i1* %t192
  %t193 = load i32*, i32** %t187
  %t194 = load i32, i32* %t191
  store i32 %t194, i32* @.len.knight_tour_warnsdorff.p0
  %t195 = call i1 @knight_tour_warnsdorff(i32* %t193, i32 0, i32 0)
  store i1 %t195, i1* %t192
  %t196 = load i1, i1* %t192
  br i1 %t196, label %then.61, label %else.62
then.61:
  %t197 = getelementptr inbounds [27 x i8], [27 x i8]* @.str.7278d4, i32 0, i32 0
%t198 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t198, i8* %t197)
  %t199 = load i32*, i32** %t187
  %t200 = load i32, i32* %t191
  store i32 %t200, i32* @.len.print_board.p0
  call void @print_board(i32* %t199)
  br label %endif.63
else.62:
  %t201 = getelementptr inbounds [42 x i8], [42 x i8]* @.str.c71474, i32 0, i32 0
%t202 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t202, i8* %t201)
  br label %endif.63
endif.63:
  ret i32 0
endfn.60:
  ret i32 0
}

