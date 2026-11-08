import type { RefObject } from "react"

type BirdProps = {
  headRef: RefObject<SVGGElement | null>
  eyeLeftRef: RefObject<SVGGElement | null>
  eyeRightRef: RefObject<SVGGElement | null>
  pupilLeftRef: RefObject<SVGGElement | null>
  pupilRightRef: RefObject<SVGGElement | null>
  browLeftRef: RefObject<SVGGElement | null>
  browRightRef: RefObject<SVGGElement | null>
  beakLowerRef: RefObject<SVGGElement | null>
  wingLeftRef: RefObject<SVGGElement | null>
  wingRightRef: RefObject<SVGGElement | null>
  footLeftRef: RefObject<SVGGElement | null>
  footRightRef: RefObject<SVGGElement | null>
}

/**
 * "ANGERY" — a hand-drawn, production-style 3D vector bird.
 * Everything is code: layered radial gradients, rim light, ambient
 * occlusion, specular sheen and drop shadows build the volume.
 */
export default function BirdMascot({
  headRef,
  eyeLeftRef,
  eyeRightRef,
  pupilLeftRef,
  pupilRightRef,
  browLeftRef,
  browRightRef,
  beakLowerRef,
  wingLeftRef,
  wingRightRef,
  footLeftRef,
  footRightRef,
}: BirdProps) {
  return (
    <svg viewBox="0 0 260 260" width="260" height="260" xmlns="http://www.w3.org/2000/svg" style={{ overflow: "visible" }}>
      <defs>
        {/* ── Body volume ── */}
        <radialGradient id="abBody" cx="30%" cy="20%" r="88%">
          <stop offset="0%" stopColor="#FFB08F" />
          <stop offset="14%" stopColor="#FF7A55" />
          <stop offset="38%" stopColor="#EE3B22" />
          <stop offset="66%" stopColor="#C6180B" />
          <stop offset="87%" stopColor="#910C05" />
          <stop offset="100%" stopColor="#5E0502" />
        </radialGradient>
        <radialGradient id="abHead" cx="33%" cy="24%" r="82%">
          <stop offset="0%" stopColor="#FFA07C" />
          <stop offset="20%" stopColor="#FA5B39" />
          <stop offset="52%" stopColor="#DB2513" />
          <stop offset="80%" stopColor="#A81107" />
          <stop offset="100%" stopColor="#6D0703" />
        </radialGradient>
        <linearGradient id="abAO" x1="0" y1="0" x2="0.7" y2="1">
          <stop offset="0%" stopColor="#5E0502" stopOpacity="0" />
          <stop offset="62%" stopColor="#5E0502" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#3A0301" stopOpacity="0.42" />
        </linearGradient>
        <radialGradient id="abBelly" cx="40%" cy="22%" r="80%">
          <stop offset="0%" stopColor="#FFFDF2" />
          <stop offset="34%" stopColor="#FBE9C4" />
          <stop offset="72%" stopColor="#E8C690" />
          <stop offset="100%" stopColor="#BE9358" />
        </radialGradient>
        {/* ── Wings / tail ── */}
        <linearGradient id="abWing" x1="0.1" y1="0" x2="0.9" y2="1">
          <stop offset="0%" stopColor="#FF7A55" />
          <stop offset="32%" stopColor="#DC2A16" />
          <stop offset="70%" stopColor="#A01006" />
          <stop offset="100%" stopColor="#5C0502" />
        </linearGradient>
        <linearGradient id="abTail" x1="0.1" y1="0" x2="1" y2="0.9">
          <stop offset="0%" stopColor="#D6220F" />
          <stop offset="56%" stopColor="#8E0C05" />
          <stop offset="100%" stopColor="#4E0402" />
        </linearGradient>
        {/* ── Beak ── */}
        <linearGradient id="abBeakTop" x1="0.2" y1="0" x2="0.78" y2="1">
          <stop offset="0%" stopColor="#FFE9A0" />
          <stop offset="16%" stopColor="#FFC94E" />
          <stop offset="42%" stopColor="#FFA51F" />
          <stop offset="70%" stopColor="#EE7C05" />
          <stop offset="100%" stopColor="#B44F02" />
        </linearGradient>
        <linearGradient id="abBeakLow" x1="0.3" y1="0" x2="0.7" y2="1">
          <stop offset="0%" stopColor="#F09B22" />
          <stop offset="48%" stopColor="#C86405" />
          <stop offset="100%" stopColor="#7A3601" />
        </linearGradient>
        {/* ── Eyes ── */}
        <radialGradient id="abSclera" cx="36%" cy="26%" r="80%">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="58%" stopColor="#FAF7F4" />
          <stop offset="86%" stopColor="#E5DAD3" />
          <stop offset="100%" stopColor="#C3B3A9" />
        </radialGradient>
        <radialGradient id="abIris" cx="34%" cy="28%" r="74%">
          <stop offset="0%" stopColor="#B98349" />
          <stop offset="30%" stopColor="#7B4E24" />
          <stop offset="66%" stopColor="#3B2210" />
          <stop offset="100%" stopColor="#150C05" />
        </radialGradient>
        <linearGradient id="abBrow" x1="0" y1="0" x2="0.2" y2="1">
          <stop offset="0%" stopColor="#8A3521" />
          <stop offset="40%" stopColor="#4A150C" />
          <stop offset="100%" stopColor="#1B0603" />
        </linearGradient>
        <linearGradient id="abFoot" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FFD766" />
          <stop offset="48%" stopColor="#FBA919" />
          <stop offset="100%" stopColor="#C26605" />
        </linearGradient>
        <radialGradient id="abCheek" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FF7C63" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#FF7C63" stopOpacity="0" />
        </radialGradient>
        {/* warm halo so the character floats off the white page */}
        <radialGradient id="abHalo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FF9C74" stopOpacity="0.3" />
          <stop offset="55%" stopColor="#FFB48F" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#FFB48F" stopOpacity="0" />
        </radialGradient>

        <filter id="abBlur" x="-70%" y="-70%" width="240%" height="240%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
        <filter id="abBlur2" x="-70%" y="-70%" width="240%" height="240%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
        <filter id="abShadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="12" stdDeviation="10" floodColor="#4A0402" floodOpacity="0.4" />
        </filter>
        <filter id="abInner" x="-40%" y="-40%" width="180%" height="180%">
          <feOffset dx="0" dy="3" />
          <feGaussianBlur stdDeviation="3" result="b" />
          <feComposite in="SourceGraphic" in2="b" operator="out" result="o" />
          <feColorMatrix in="o" type="matrix" values="0 0 0 0 0.25  0 0 0 0 0.03  0 0 0 0 0.01  0 0 0 0.55 0" />
        </filter>
        <clipPath id="abEyeClipL"><ellipse cx="112" cy="86" rx="15.5" ry="16.5" /></clipPath>
        <clipPath id="abEyeClipR"><ellipse cx="150" cy="86" rx="15.5" ry="16.5" /></clipPath>
      </defs>

      <g filter="url(#abShadow)">
        {/* ═══ TAIL — three fanned feathers, individually hinged ═══ */}
        <g data-tail="1">
          <path d="M94 158 Q56 146 30 160 Q56 180 94 180 Z" fill="url(#abTail)" stroke="#4A0402" strokeWidth="2" strokeLinejoin="round" />
          <path d="M88 162 Q58 154 38 161" stroke="#FF9268" strokeWidth="2.2" fill="none" strokeLinecap="round" opacity="0.5" />
        </g>
        <g data-tail="2">
          <path d="M92 174 Q52 172 24 192 Q54 210 96 196 Z" fill="url(#abTail)" stroke="#4A0402" strokeWidth="2" strokeLinejoin="round" />
          <path d="M88 179 Q56 180 32 193" stroke="#FF9268" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.34" />
        </g>
        <g data-tail="3">
          <path d="M96 188 Q62 196 42 222 Q74 228 104 202 Z" fill="url(#abTail)" stroke="#4A0402" strokeWidth="2" strokeLinejoin="round" />
          <path d="M96 193 Q70 201 52 218" stroke="#FF9268" strokeWidth="1.9" fill="none" strokeLinecap="round" opacity="0.24" />
        </g>

        {/* ═══ BODY ═══ */}
        <ellipse cx="134" cy="160" rx="66" ry="58" fill="url(#abBody)" />
        <ellipse cx="134" cy="160" rx="66" ry="58" fill="url(#abAO)" />
        {/* velvet rim defines the silhouette */}
        <ellipse cx="134" cy="160" rx="65" ry="57" fill="none" stroke="#4E0402" strokeOpacity="0.34" strokeWidth="2.6" />
        {/* rim light, lower right */}
        <path d="M188 168 Q198 196 164 210 Q188 196 178 166 Z" fill="#FF9E6E" opacity="0.5" filter="url(#abBlur2)" />
        <path d="M186 150 Q200 174 186 196" stroke="#FFC9A8" strokeWidth="3" fill="none" opacity="0.3" strokeLinecap="round" />
        {/* key light on shoulder */}
        <ellipse cx="96" cy="126" rx="26" ry="15" fill="#FFFFFF" opacity="0.24" filter="url(#abBlur)" transform="rotate(-26 96 126)" />
        <ellipse cx="90" cy="120" rx="10" ry="5.5" fill="#FFFFFF" opacity="0.5" transform="rotate(-26 90 120)" />

        {/* ═══ BELLY CHEST ═══ */}
        <ellipse cx="134" cy="182" rx="43" ry="32" fill="url(#abBelly)" />
        <ellipse cx="134" cy="182" rx="43" ry="32" fill="none" stroke="#9C6A33" strokeOpacity="0.32" strokeWidth="2" />
        {/* feather scallops */}
        <path d="M112 203 Q120 209 128 203 Q136 209 144 203 Q152 209 158 204" stroke="#C79C61" strokeWidth="2" fill="none" opacity="0.55" strokeLinecap="round" />
        <path d="M118 194 Q125 199 132 194 Q139 199 146 194" stroke="#C79C61" strokeWidth="1.7" fill="none" opacity="0.35" strokeLinecap="round" />
        <ellipse cx="119" cy="169" rx="18" ry="9" fill="#FFFFFF" opacity="0.5" filter="url(#abBlur2)" transform="rotate(-16 119 169)" />
        {/* soft neck shadow so the head sits proud of the body */}
        <ellipse cx="132" cy="146" rx="47" ry="12" fill="#4A0402" opacity="0.22" filter="url(#abBlur)" />
        {/* wing sockets — occlusion where the wings meet the torso */}
        <ellipse cx="92" cy="146" rx="16" ry="24" fill="#5C0502" opacity="0.2" filter="url(#abBlur2)" />
        <ellipse cx="176" cy="146" rx="16" ry="24" fill="#5C0502" opacity="0.2" filter="url(#abBlur2)" />

        {/* ═══ FEET ═══ */}
        <g ref={footLeftRef} strokeLinecap="round" strokeLinejoin="round">
          <path d="M116 206 L112 222" stroke="url(#abFoot)" strokeWidth="9" fill="none" />
          <path d="M112 222 L100 230" stroke="url(#abFoot)" strokeWidth="7" fill="none" />
          <path d="M112 222 L113 232" stroke="url(#abFoot)" strokeWidth="7" fill="none" />
          <path d="M112 222 L124 230" stroke="url(#abFoot)" strokeWidth="7" fill="none" />
        </g>
        <g ref={footRightRef} strokeLinecap="round" strokeLinejoin="round">
          <path d="M152 206 L156 222" stroke="url(#abFoot)" strokeWidth="9" fill="none" />
          <path d="M156 222 L144 230" stroke="url(#abFoot)" strokeWidth="7" fill="none" />
          <path d="M156 222 L157 232" stroke="url(#abFoot)" strokeWidth="7" fill="none" />
          <path d="M156 222 L168 230" stroke="url(#abFoot)" strokeWidth="7" fill="none" />
        </g>

        {/* ═══ HEAD + FACE (tracks the pointer) ═══ */}
        <g ref={headRef}>
          {/* neck occlusion */}
          <ellipse cx="134" cy="142" rx="40" ry="9" fill="#5C0502" opacity="0.3" filter="url(#abBlur2)" />
          <circle cx="130" cy="90" r="50" fill="url(#abHead)" />
          <circle cx="130" cy="90" r="50" fill="url(#abAO)" opacity="0.7" />
          <circle cx="130" cy="90" r="49" fill="none" stroke="#4E0402" strokeOpacity="0.3" strokeWidth="2.4" />

          {/* crest feathers — springy, hinged at the scalp */}
          <g data-crest="1">
            <path d="M120 44 Q112 16 124 2 Q134 22 130 46 Z" fill="#8E0C05" stroke="#4A0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M122 42 Q117 24 124 12" stroke="#FFA37D" strokeWidth="2.3" fill="none" strokeLinecap="round" opacity="0.5" />
          </g>
          <g data-crest="2">
            <path d="M136 44 Q146 14 164 8 Q148 30 144 48 Z" fill="#660703" stroke="#4A0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M138 44 Q146 24 157 17" stroke="#FFA37D" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.3" />
          </g>
          <g data-crest="3">
            <path d="M142 50 Q166 38 178 50 Q158 56 146 60 Z" fill="#8E0C05" stroke="#4A0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M148 52 Q166 45 174 50" stroke="#FFA37D" strokeWidth="1.8" fill="none" strokeLinecap="round" opacity="0.28" />
          </g>

          {/* head sheen */}
          <ellipse cx="106" cy="62" rx="21" ry="11" fill="#FFFFFF" opacity="0.26" filter="url(#abBlur2)" transform="rotate(-24 106 62)" />
          <ellipse cx="102" cy="58" rx="8" ry="4" fill="#FFFFFF" opacity="0.4" transform="rotate(-24 102 58)" />
          <ellipse cx="160" cy="66" rx="14" ry="8" fill="#FFFFFF" opacity="0.12" filter="url(#abBlur2)" />

          {/* cheeks */}
          <ellipse cx="98" cy="106" rx="13" ry="8" fill="url(#abCheek)" />
          <ellipse cx="162" cy="106" rx="13" ry="8" fill="url(#abCheek)" />

          {/* eye whites with subtle angry tilt */}
          <g transform="rotate(-5 112 86)">
            <g ref={eyeLeftRef}>
              <ellipse cx="112" cy="86" rx="15.5" ry="16.5" fill="url(#abSclera)" stroke="#3B0A05" strokeWidth="2.6" />
              <ellipse cx="112" cy="86" rx="15.5" ry="16.5" fill="none" stroke="#000" strokeOpacity="0.18" strokeWidth="1" />
              <ellipse cx="112" cy="76" rx="13" ry="6" fill="#6D0703" opacity="0.22" clipPath="url(#abEyeClipL)" />
              <g ref={pupilLeftRef}>
                <circle cx="112" cy="88" r="9" fill="url(#abIris)" />
                <circle cx="112" cy="88" r="4.6" fill="#0B0603" />
                <circle cx="108.4" cy="84" r="3.1" fill="#fff" />
                <circle cx="116" cy="92" r="1.5" fill="#fff" opacity="0.6" />
              </g>
              <ellipse cx="106" cy="79" rx="3.4" ry="1.8" fill="#fff" opacity="0.9" transform="rotate(-24 106 79)" />
            </g>
          </g>
          <g transform="rotate(5 150 86)">
            <g ref={eyeRightRef}>
              <ellipse cx="150" cy="86" rx="15.5" ry="16.5" fill="url(#abSclera)" stroke="#3B0A05" strokeWidth="2.6" />
              <ellipse cx="150" cy="86" rx="15.5" ry="16.5" fill="none" stroke="#000" strokeOpacity="0.18" strokeWidth="1" />
              <ellipse cx="150" cy="76" rx="13" ry="6" fill="#6D0703" opacity="0.22" clipPath="url(#abEyeClipR)" />
              <g ref={pupilRightRef}>
                <circle cx="150" cy="88" r="9" fill="url(#abIris)" />
                <circle cx="150" cy="88" r="4.6" fill="#0B0603" />
                <circle cx="146.4" cy="84" r="3.1" fill="#fff" />
                <circle cx="154" cy="92" r="1.5" fill="#fff" opacity="0.6" />
              </g>
              <ellipse cx="144" cy="79" rx="3.4" ry="1.8" fill="#fff" opacity="0.9" transform="rotate(-24 144 79)" />
            </g>
          </g>

          {/* heavy angry brows */}
          <g ref={browLeftRef}>
            <path d="M88 58 Q104 54 122 74" stroke="url(#abBrow)" strokeWidth="14" strokeLinecap="round" fill="none" />
            <path d="M94 56 Q106 55 118 68" stroke="#C4664A" strokeWidth="2.4" strokeLinecap="round" fill="none" opacity="0.5" />
          </g>
          <g ref={browRightRef}>
            <path d="M172 58 Q156 54 138 74" stroke="url(#abBrow)" strokeWidth="14" strokeLinecap="round" fill="none" />
            <path d="M166 56 Q154 55 142 68" stroke="#C4664A" strokeWidth="2.4" strokeLinecap="round" fill="none" opacity="0.5" />
          </g>
          {/* shadow the brows cast on the face */}
          <path d="M96 74 Q110 72 122 82" stroke="#4A0402" strokeWidth="3" fill="none" opacity="0.2" strokeLinecap="round" />
          <path d="M164 74 Q150 72 138 82" stroke="#4A0402" strokeWidth="3" fill="none" opacity="0.2" strokeLinecap="round" />

          {/* head feather texture */}
          <path d="M84 84 Q90 78 96 80" stroke="#8E0C05" strokeWidth="2.2" fill="none" opacity="0.4" strokeLinecap="round" />
          <path d="M80 98 Q86 92 93 94" stroke="#8E0C05" strokeWidth="2" fill="none" opacity="0.3" strokeLinecap="round" />
          <path d="M104 52 Q112 44 121 46" stroke="#FFB295" strokeWidth="2.2" fill="none" opacity="0.35" strokeLinecap="round" />
          <path d="M148 54 Q156 48 164 52" stroke="#FFB295" strokeWidth="2" fill="none" opacity="0.22" strokeLinecap="round" />
          <path d="M168 96 Q176 100 177 108" stroke="#8E0C05" strokeWidth="2.2" fill="none" opacity="0.35" strokeLinecap="round" />

          {/* mouth void (behind the beak) */}
          <ellipse cx="130" cy="116" rx="15" ry="9" fill="#4B0A04" />

          {/* lower beak */}
          <g ref={beakLowerRef}>
            <path d="M114 116 Q130 112 146 116 Q144 132 130 140 Q116 132 114 116 Z" fill="url(#abBeakLow)" stroke="#7C3702" strokeWidth="2.2" strokeLinejoin="round" />
            <path d="M121 130 Q130 137 139 130" stroke="#FFB35C" strokeWidth="1.8" fill="none" opacity="0.55" strokeLinecap="round" />
            <ellipse cx="130" cy="132" rx="6" ry="3" fill="#E5725A" opacity="0.75" />
          </g>

          {/* upper beak */}
          <g>
            <path d="M104 104 Q130 96 156 104 Q150 126 130 144 Q110 126 104 104 Z" fill="url(#abBeakTop)" stroke="#8A4203" strokeWidth="2.6" strokeLinejoin="round" />
            {/* sheen */}
            <path d="M112 106 Q128 100 146 106 Q140 114 130 118 Q120 114 112 106 Z" fill="#FFFBDE" opacity="0.55" />
            <path d="M110 105 Q128 98 150 104" stroke="#FFFCE8" strokeWidth="2" fill="none" opacity="0.65" strokeLinecap="round" />
            {/* nostrils */}
            <ellipse cx="122" cy="109" rx="2.3" ry="1.4" fill="#8F4A05" opacity="0.75" transform="rotate(-16 122 109)" />
            <ellipse cx="138" cy="109" rx="2.3" ry="1.4" fill="#8F4A05" opacity="0.75" transform="rotate(16 138 109)" />
            {/* beak centre ridge */}
            <path d="M130 102 L130 134" stroke="#C97710" strokeWidth="1.4" opacity="0.4" />
            <path d="M130 142 Q118 134 112 124" stroke="#9A4D02" strokeWidth="2" fill="none" opacity="0.35" strokeLinecap="round" />
          </g>

          {/* friendly smirk corners */}
          <path d="M150 112 Q158 114 160 120" stroke="#4A0402" strokeWidth="2.4" fill="none" opacity="0.35" strokeLinecap="round" />
        </g>

        {/* ═══ LEFT WING — articulated: arm + four hinged primaries ═══ */}
        <g ref={wingLeftRef}>
          {/* shoulder / covert block */}
          <path d="M84 122 Q48 100 28 116 Q18 136 36 152 Q58 166 86 158 Q72 140 84 122 Z" fill="url(#abWing)" stroke="#4E0402" strokeWidth="2.4" strokeLinejoin="round" />
          <path d="M70 132 Q46 122 32 132 Q44 144 68 142 Z" fill="#FF8A62" opacity="0.34" />
          <path d="M64 128 Q46 118 34 124" stroke="#FFD8C2" strokeWidth="2.2" fill="none" opacity="0.32" strokeLinecap="round" />
          <path d="M58 144 Q42 146 34 154" stroke="#4E0402" strokeWidth="2.2" fill="none" opacity="0.32" strokeLinecap="round" />

          {/* primaries — each one hinged so they ripple in flight */}
          <g data-feather="left">
            <path d="M62 142 Q34 138 12 154 Q32 166 64 156 Z" fill="url(#abTail)" stroke="#4E0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M56 145 Q36 143 22 152" stroke="#FF9268" strokeWidth="2.2" fill="none" opacity="0.45" strokeLinecap="round" />
          </g>
          <g data-feather="left">
            <path d="M58 154 Q30 158 14 178 Q38 186 66 166 Z" fill="url(#abWing)" stroke="#4E0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M52 159 Q32 164 22 176" stroke="#FF9268" strokeWidth="2.1" fill="none" opacity="0.4" strokeLinecap="round" />
          </g>
          <g data-feather="left">
            <path d="M64 164 Q40 176 30 196 Q54 196 74 174 Z" fill="url(#abTail)" stroke="#4E0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M60 168 Q44 178 38 190" stroke="#FF9268" strokeWidth="2" fill="none" opacity="0.35" strokeLinecap="round" />
          </g>
          <g data-feather="left">
            <path d="M76 170 Q58 186 54 204 Q74 198 86 178 Z" fill="url(#abWing)" stroke="#4E0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M76 174 Q64 184 60 196" stroke="#FF9268" strokeWidth="1.9" fill="none" opacity="0.32" strokeLinecap="round" />
          </g>
        </g>

        {/* ═══ RIGHT WING — mirrored articulation ═══ */}
        <g ref={wingRightRef}>
          <path d="M176 122 Q212 100 232 116 Q242 136 224 152 Q202 166 174 158 Q188 140 176 122 Z" fill="url(#abWing)" stroke="#4E0402" strokeWidth="2.4" strokeLinejoin="round" />
          <path d="M190 132 Q214 122 228 132 Q216 144 192 142 Z" fill="#FF8A62" opacity="0.34" />
          <path d="M196 128 Q214 118 226 124" stroke="#FFD8C2" strokeWidth="2.2" fill="none" opacity="0.32" strokeLinecap="round" />
          <path d="M202 144 Q218 146 226 154" stroke="#4E0402" strokeWidth="2.2" fill="none" opacity="0.32" strokeLinecap="round" />

          <g data-feather="right">
            <path d="M198 142 Q226 138 248 154 Q228 166 196 156 Z" fill="url(#abTail)" stroke="#4E0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M204 145 Q224 143 238 152" stroke="#FF9268" strokeWidth="2.2" fill="none" opacity="0.45" strokeLinecap="round" />
          </g>
          <g data-feather="right">
            <path d="M202 154 Q230 158 246 178 Q222 186 194 166 Z" fill="url(#abWing)" stroke="#4E0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M208 159 Q228 164 238 176" stroke="#FF9268" strokeWidth="2.1" fill="none" opacity="0.4" strokeLinecap="round" />
          </g>
          <g data-feather="right">
            <path d="M196 164 Q220 176 230 196 Q206 196 186 174 Z" fill="url(#abTail)" stroke="#4E0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M200 168 Q216 178 222 190" stroke="#FF9268" strokeWidth="2" fill="none" opacity="0.35" strokeLinecap="round" />
          </g>
          <g data-feather="right">
            <path d="M184 170 Q202 186 206 204 Q186 198 174 178 Z" fill="url(#abWing)" stroke="#4E0402" strokeWidth="2" strokeLinejoin="round" />
            <path d="M184 174 Q196 184 200 196" stroke="#FF9268" strokeWidth="1.9" fill="none" opacity="0.32" strokeLinecap="round" />
          </g>
        </g>
      </g>
    </svg>
  )
}
