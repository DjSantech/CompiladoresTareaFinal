declare i32 @printf(i8*, ...)
declare i8* @malloc(i32)

@.fmt_int   = private unnamed_addr constant [4 x i8] c"%d\0A\00"
@.fmt_float = private unnamed_addr constant [4 x i8] c"%f\0A\00"
@.fmt_char  = private unnamed_addr constant [4 x i8] c"%c\0A\00"
@.fmt_str   = private unnamed_addr constant [4 x i8] c"%s\0A\00"
@.len.print_board.p0 = global i32 0
@.len.knight_tour_warnsdorff.p0 = global i32 0
@.str.65e58c = private unnamed_addr constant [42 x i8] [i8 78, i8 111, i8 32, i8 115, i8 101, i8 32, i8 112, i8 117, i8 100, i8 111, i8 32, i8 99, i8 111, i8 109, i8 112, i8 108, i8 101, i8 116, i8 97, i8 114, i8 32, i8 101, i8 108, i8 32, i8 116, i8 111, i8 117, i8 114, i8 32, i8 100, i8 101, i8 115, i8 100, i8 101, i8 32, i8 40, i8 48, i8 44, i8 48, i8 41, i8 10, i8 0]
@.str.c278a0 = private unnamed_addr constant [27 x i8] [i8 84, i8 111, i8 117, i8 114, i8 32, i8 99, i8 111, i8 109, i8 112, i8 108, i8 101, i8 116, i8 111, i8 32, i8 101, i8 110, i8 99, i8 111, i8 110, i8 116, i8 114, i8 97, i8 100, i8 111, i8 58, i8 10, i8 0]
@.str.1cad2d = private unnamed_addr constant [2 x i8] [i8 10, i8 0]
@.str.6b7613 = private unnamed_addr constant [2 x i8] [i8 32, i8 0]

@N = global i32 8
@KNIGHT_DX = global i32* null
@KNIGHT_DY = global i32* null
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
  %t26 = load i32, i32* %t22
  %t27 = load i32, i32* %t23
  %t28 = call i1 @in_board(i32 %t26, i32 %t27)
  br i1 %t28, label %then.10, label %else.11
then.10:
  ret i1 0
  br label %endif.12
else.11:
  br label %endif.12
endif.12:
  %t29 = load i32, i32* %t22
  %t30 = load i32, i32* %t23
  %t31 = call i32 @index_of(i32 %t29, i32 %t30)
  store i32 %t31, i32* %t25
  %t32 = load i32*, i32** %t24
  %t33 = getelementptr inbounds i32, i32* %t32, i32 0
  %t34 = load i32, i32* %t33
  %t35 = icmp ne i32 %t34, 0
  br i1 %t35, label %then.13, label %else.14
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
  %t36 = alloca i32
  store i32 %x, i32* %t36
  %t37 = alloca i32
  store i32 %y, i32* %t37
  %t38 = alloca i32*
  store i32* %board, i32** %t38
  %t39 = alloca i32
  store i32 0, i32* %t39
  %t40 = alloca i32
  store i32 0, i32* %t40
  %t41 = alloca i32
  store i32 0, i32* %t41
  %t42 = alloca i32
  store i32 0, i32* %t42
  store i32 0, i32* %t40
  br label %for.head.17
for.head.17:
  %t43 = load i32, i32* %t40
  %t44 = icmp slt i32 %t43, 8
  br i1 %t44, label %for.body.18, label %for.end.20
for.body.18:
  %t45 = load i32, i32* %t36
  %t46 = bitcast i8* null to i32*
  %t47 = getelementptr inbounds i32, i32* %t46, i32 0
  %t48 = load i32, i32* %t47
  %t49 = add i32 %t45, %t48
  store i32 %t49, i32* %t41
  %t50 = load i32, i32* %t37
  %t51 = bitcast i8* null to i32*
  %t52 = getelementptr inbounds i32, i32* %t51, i32 0
  %t53 = load i32, i32* %t52
  %t54 = add i32 %t50, %t53
  store i32 %t54, i32* %t42
  %t55 = load i32, i32* %t41
  %t56 = load i32, i32* %t42
  %t57 = load i32*, i32** %t38
  %t58 = call i1 @is_valid_move(i32 %t55, i32 %t56, i32* %t57)
  br i1 %t58, label %then.21, label %else.22
then.21:
  %t59 = load i32, i32* %t39
  %t60 = add i32 %t59, 1
  store i32 %t60, i32* %t39
  br label %endif.23
else.22:
  br label %endif.23
endif.23:
  br label %for.step.19
for.step.19:
  %t61 = load i32, i32* %t40
  %t62 = add i32 %t61, 1
  store i32 %t62, i32* %t40
  br label %for.head.17
for.end.20:
  %t63 = load i32, i32* %t39
  ret i32 %t63
endfn.16:
  ret i32 0
}

define i32 @warnsdorff_next(i32 %x, i32 %y, i32* %board) {
  %t64 = alloca i32
  store i32 %x, i32* %t64
  %t65 = alloca i32
  store i32 %y, i32* %t65
  %t66 = alloca i32*
  store i32* %board, i32** %t66
  %t67 = alloca i32
  store i32 0, i32* %t67
  %t68 = alloca i32
  %t69 = sub i32 0, 1
  store i32 %t69, i32* %t68
  %t70 = alloca i32
  store i32 9, i32* %t70
  %t71 = alloca i32
  store i32 0, i32* %t71
  %t72 = alloca i32
  store i32 0, i32* %t72
  %t73 = alloca i32
  store i32 0, i32* %t73
  store i32 0, i32* %t67
  br label %for.head.25
for.head.25:
  %t74 = load i32, i32* %t67
  %t75 = icmp slt i32 %t74, 8
  br i1 %t75, label %for.body.26, label %for.end.28
for.body.26:
  %t76 = load i32, i32* %t64
  %t77 = bitcast i8* null to i32*
  %t78 = getelementptr inbounds i32, i32* %t77, i32 0
  %t79 = load i32, i32* %t78
  %t80 = add i32 %t76, %t79
  store i32 %t80, i32* %t71
  %t81 = load i32, i32* %t65
  %t82 = bitcast i8* null to i32*
  %t83 = getelementptr inbounds i32, i32* %t82, i32 0
  %t84 = load i32, i32* %t83
  %t85 = add i32 %t81, %t84
  store i32 %t85, i32* %t72
  %t86 = load i32, i32* %t71
  %t87 = load i32, i32* %t72
  %t88 = load i32*, i32** %t66
  %t89 = call i1 @is_valid_move(i32 %t86, i32 %t87, i32* %t88)
  br i1 %t89, label %then.29, label %else.30
then.29:
  %t90 = load i32, i32* %t71
  %t91 = load i32, i32* %t72
  %t92 = load i32*, i32** %t66
  %t93 = call i32 @degree_of(i32 %t90, i32 %t91, i32* %t92)
  store i32 %t93, i32* %t73
  %t94 = load i32, i32* %t73
  %t95 = load i32, i32* %t70
  %t96 = icmp slt i32 %t94, %t95
  br i1 %t96, label %then.32, label %else.33
then.32:
  %t97 = load i32, i32* %t73
  store i32 %t97, i32* %t70
  %t98 = load i32, i32* %t67
  store i32 %t98, i32* %t68
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
  %t99 = load i32, i32* %t67
  %t100 = add i32 %t99, 1
  store i32 %t100, i32* %t67
  br label %for.head.25
for.end.28:
  %t101 = load i32, i32* %t68
  ret i32 %t101
endfn.24:
  ret i32 0
}

define i32 @knight_step_warnsdorff(i32 %curr_pos, i32* %board) {
  %t102 = alloca i32
  store i32 %curr_pos, i32* %t102
  %t103 = alloca i32*
  store i32* %board, i32** %t103
  %t104 = alloca i32
  store i32 0, i32* %t104
  %t105 = alloca i32
  store i32 0, i32* %t105
  %t106 = alloca i32
  store i32 0, i32* %t106
  %t107 = alloca i32
  store i32 0, i32* %t107
  %t108 = alloca i32
  store i32 0, i32* %t108
  %t109 = load i32, i32* %t102
  %t110 = load i32, i32* @N
  %t111 = srem i32 %t109, %t110
  store i32 %t111, i32* %t104
  %t112 = load i32, i32* %t102
  %t113 = load i32, i32* @N
  %t114 = sdiv i32 %t112, %t113
  store i32 %t114, i32* %t105
  %t115 = load i32, i32* %t104
  %t116 = load i32, i32* %t105
  %t117 = load i32*, i32** %t103
  %t118 = call i32 @warnsdorff_next(i32 %t115, i32 %t116, i32* %t117)
  store i32 %t118, i32* %t106
  %t119 = load i32, i32* %t106
  %t120 = icmp slt i32 %t119, 0
  br i1 %t120, label %then.36, label %else.37
then.36:
  %t121 = sub i32 0, 1
  ret i32 %t121
  br label %endif.38
else.37:
  br label %endif.38
endif.38:
  %t122 = load i32, i32* %t104
  %t123 = bitcast i8* null to i32*
  %t124 = getelementptr inbounds i32, i32* %t123, i32 0
  %t125 = load i32, i32* %t124
  %t126 = add i32 %t122, %t125
  store i32 %t126, i32* %t107
  %t127 = load i32, i32* %t105
  %t128 = bitcast i8* null to i32*
  %t129 = getelementptr inbounds i32, i32* %t128, i32 0
  %t130 = load i32, i32* %t129
  %t131 = add i32 %t127, %t130
  store i32 %t131, i32* %t108
  %t132 = load i32, i32* %t107
  %t133 = load i32, i32* %t108
  %t134 = call i32 @index_of(i32 %t132, i32 %t133)
  ret i32 %t134
endfn.35:
  ret i32 0
}

define void @print_board(i32* %board) {
  %t135 = alloca i32*
  store i32* %board, i32** %t135
  %t136 = alloca i32
  store i32 0, i32* %t136
  %t137 = alloca i32
  store i32 0, i32* %t137
  %t138 = alloca i32
  store i32 0, i32* %t138
  store i32 0, i32* %t136
  br label %for.head.40
for.head.40:
  %t139 = load i32, i32* %t136
  %t140 = load i32, i32* @N
  %t141 = icmp slt i32 %t139, %t140
  br i1 %t141, label %for.body.41, label %for.end.43
for.body.41:
  store i32 0, i32* %t137
  br label %for.head.44
for.head.44:
  %t142 = load i32, i32* %t137
  %t143 = load i32, i32* @N
  %t144 = icmp slt i32 %t142, %t143
  br i1 %t144, label %for.body.45, label %for.end.47
for.body.45:
  %t145 = load i32, i32* %t137
  %t146 = load i32, i32* %t136
  %t147 = call i32 @index_of(i32 %t145, i32 %t146)
  store i32 %t147, i32* %t138
  %t148 = load i32*, i32** %t135
  %t149 = getelementptr inbounds i32, i32* %t148, i32 0
  %t150 = load i32, i32* %t149
%t151 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_int, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t151, i32 %t150)
  %t152 = getelementptr inbounds [2 x i8], [2 x i8]* @.str.6b7613, i32 0, i32 0
%t153 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t153, i8* %t152)
  br label %for.step.46
for.step.46:
  %t154 = load i32, i32* %t137
  %t155 = add i32 %t154, 1
  store i32 %t155, i32* %t137
  br label %for.head.44
for.end.47:
  %t156 = getelementptr inbounds [2 x i8], [2 x i8]* @.str.1cad2d, i32 0, i32 0
%t157 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t157, i8* %t156)
  br label %for.step.42
for.step.42:
  %t158 = load i32, i32* %t136
  %t159 = add i32 %t158, 1
  store i32 %t159, i32* %t136
  br label %for.head.40
for.end.43:
endfn.39:
  ret void
}

define i1 @knight_tour_warnsdorff(i32* %board, i32 %start_x, i32 %start_y) {
  %t160 = alloca i32*
  store i32* %board, i32** %t160
  %t161 = alloca i32
  store i32 %start_x, i32* %t161
  %t162 = alloca i32
  store i32 %start_y, i32* %t162
  %t163 = alloca i32
  %t164 = load i32, i32* @N
  %t165 = load i32, i32* @N
  %t166 = mul i32 %t164, %t165
  store i32 %t166, i32* %t163
  %t167 = alloca i32
  store i32 0, i32* %t167
  %t168 = alloca i32
  store i32 0, i32* %t168
  %t169 = alloca i32
  store i32 0, i32* %t169
  store i32 0, i32* %t169
  br label %for.head.49
for.head.49:
  %t170 = load i32, i32* %t169
  %t171 = load i32, i32* %t163
  %t172 = icmp slt i32 %t170, %t171
  br i1 %t172, label %for.body.50, label %for.end.52
for.body.50:
  %t173 = load i32*, i32** %t160
  %t174 = getelementptr inbounds i32, i32* %t173, i32 0
  store i32 0, i32* %t174
  br label %for.step.51
for.step.51:
  %t175 = load i32, i32* %t169
  %t176 = add i32 %t175, 1
  store i32 %t176, i32* %t169
  br label %for.head.49
for.end.52:
  %t177 = load i32, i32* %t161
  %t178 = load i32, i32* %t162
  %t179 = call i32 @index_of(i32 %t177, i32 %t178)
  store i32 %t179, i32* %t167
  %t180 = load i32*, i32** %t160
  %t181 = getelementptr inbounds i32, i32* %t180, i32 0
  store i32 1, i32* %t181
  store i32 2, i32* %t168
  br label %for.head.53
for.head.53:
  %t182 = load i32, i32* %t168
  %t183 = load i32, i32* %t163
  %t184 = icmp sle i32 %t182, %t183
  br i1 %t184, label %for.body.54, label %for.end.56
for.body.54:
  %t185 = load i32, i32* %t167
  %t186 = load i32*, i32** %t160
  %t187 = call i32 @knight_step_warnsdorff(i32 %t185, i32* %t186)
  store i32 %t187, i32* %t167
  %t188 = load i32, i32* %t167
  %t189 = icmp slt i32 %t188, 0
  br i1 %t189, label %then.57, label %else.58
then.57:
  ret i1 0
  br label %endif.59
else.58:
  br label %endif.59
endif.59:
  %t190 = load i32*, i32** %t160
  %t191 = getelementptr inbounds i32, i32* %t190, i32 0
  %t192 = load i32, i32* %t168
  store i32 %t192, i32* %t191
  br label %for.step.55
for.step.55:
  %t193 = load i32, i32* %t168
  %t194 = add i32 %t193, 1
  store i32 %t194, i32* %t168
  br label %for.head.53
for.end.56:
  ret i1 1
endfn.48:
  ret i1 0
}

define i32 @main() {
  %t195 = alloca i32*
  %t196 = mul i32 0, 4
  %t197 = call i8* @malloc(i32 %t196)
  %t198 = bitcast i8* %t197 to i32*
  store i32* %t198, i32** %t195
  %t199 = alloca i32
  store i32 0, i32* %t199
  %t200 = alloca i1
  store i1 0, i1* %t200
  %t201 = load i32*, i32** %t195
  %t202 = load i32, i32* %t199
  store i32 %t202, i32* @.len.knight_tour_warnsdorff.p0
  %t203 = call i1 @knight_tour_warnsdorff(i32* %t201, i32 0, i32 0)
  store i1 %t203, i1* %t200
  %t204 = load i1, i1* %t200
  br i1 %t204, label %then.61, label %else.62
then.61:
  %t205 = getelementptr inbounds [27 x i8], [27 x i8]* @.str.c278a0, i32 0, i32 0
%t206 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t206, i8* %t205)
  %t207 = load i32*, i32** %t195
  %t208 = load i32, i32* %t199
  store i32 %t208, i32* @.len.print_board.p0
  call void @print_board(i32* %t207)
  br label %endif.63
else.62:
  %t209 = getelementptr inbounds [42 x i8], [42 x i8]* @.str.65e58c, i32 0, i32 0
%t210 = getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0)
  call i32 (i8*, ...) @printf(i8* %t210, i8* %t209)
  br label %endif.63
endif.63:
  ret i32 0
endfn.60:
  ret i32 0
}

