import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import gsap from "gsap"
import BirdMascot from "./components/BirdMascot"

type FormDataType = {
  fullName: string
  email: string
  phone: string
  countryCode: string
  gender: string
  dob: string
  guardianName: string
  guardianPhone: string
  country: string
  province: string
  program: string
  subjects: string[]
  schoolRegion: string
  schoolType: string
  grade: string
  section: string
  password: string
  confirmPassword: string
  terms: boolean
  captcha: string
}

const countryStateMap: Record<string, string[]> = {
  "United States": ["California", "New York", "Texas", "Florida", "Illinois", "Washington", "Massachusetts", "Colorado"],
  "United Kingdom": ["England", "Scotland", "Wales", "Northern Ireland", "Greater London", "West Midlands"],
  "Canada": ["Ontario", "Quebec", "British Columbia", "Alberta", "Manitoba", "Nova Scotia"],
  "Australia": ["New South Wales", "Victoria", "Queensland", "Western Australia", "South Australia", "Tasmania"],
  "India": ["Maharashtra", "Karnataka", "Tamil Nadu", "Delhi", "West Bengal", "Gujarat", "Kerala", "Rajasthan"],
  "UAE": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah"],
}

const programOptions = ["O-Level", "A-Level"]
const DEFAULT_SUBJECTS = ["Maths", "Computer Science"]
const gradeOptionsByProgram: Record<string, string[]> = {
  "O-Level": ["O-Level - Grade 9", "O-Level - Grade 10", "O-Level - Grade 11"],
  "A-Level": ["A-Level - AS (Grade 12)", "A-Level - A2 (Grade 13)"],
}

const APP_NAME = (() => {
  try { return (window as unknown as { ASCEND_APP_NAME?: string }).ASCEND_APP_NAME || "ASCEND" }
  catch { return "ASCEND" }
})()

const CSRF = (() => {
  try {
    const m = document.cookie.match(/(?:^|;\s*)pms_csrf=([^;]+)/)
    return m ? decodeURIComponent(m[1]) : ""
  } catch { return "" }
})()

const BIRD = 260
const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v))

export default function App() {
  const [step, setStep] = useState(1)

  useEffect(() => { document.title = `Join ${APP_NAME}` }, [])

  /* Subjects are administrator-managed. Load the live list so anything the
     academy adds shows up here without a rebuild; fall back to the defaults
     if the request fails so the form always works. */
  const [subjectOptions, setSubjectOptions] = useState<string[]>(DEFAULT_SUBJECTS)
  useEffect(() => {
    let cancelled = false
    fetch("/api/subjects", { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (cancelled || !data || !Array.isArray(data.subjects)) return
        const clean = data.subjects.filter((x: unknown) => typeof x === "string" && x.length > 0)
        if (clean.length) setSubjectOptions(clean)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])
  const [focusedField, setFocusedField] = useState<string | null>(null)
  const [showSuccessConfetti, setShowSuccessConfetti] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [captchaA] = useState(() => Math.floor(Math.random() * 5) + 3)
  const [captchaB] = useState(() => Math.floor(Math.random() * 5) + 2)
  const [chirpText, setChirpText] = useState<string | null>(null)
  const [birdScale, setBirdScale] = useState(1)
  const [lastValidFields, setLastValidFields] = useState<Set<string>>(new Set())

  const formContainerRef = useRef<HTMLDivElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)

  /* ── Mascot refs (free-flying overlay) ── */
  const birdFlyRef = useRef<HTMLDivElement>(null)
  const birdBobRef = useRef<HTMLDivElement>(null)
  const birdBankRef = useRef<HTMLDivElement>(null)
  const birdReactRef = useRef<HTMLDivElement>(null)
  const chirpRef = useRef<HTMLDivElement>(null)
  const sparksRef = useRef<HTMLDivElement>(null)
  const trailRef = useRef<HTMLDivElement>(null)
  const headRef = useRef<SVGGElement | null>(null)
  const eyeLeftRef = useRef<SVGGElement | null>(null)
  const eyeRightRef = useRef<SVGGElement | null>(null)
  const pupilLeftRef = useRef<SVGGElement | null>(null)
  const pupilRightRef = useRef<SVGGElement | null>(null)
  const browLeftRef = useRef<SVGGElement | null>(null)
  const browRightRef = useRef<SVGGElement | null>(null)
  const beakLowerRef = useRef<SVGGElement | null>(null)
  const wingLeftRef = useRef<SVGGElement | null>(null)
  const wingRightRef = useRef<SVGGElement | null>(null)
  const footLeftRef = useRef<SVGGElement | null>(null)
  const footRightRef = useRef<SVGGElement | null>(null)

  const focusElRef = useRef<HTMLElement | null>(null)
  const pointerRef = useRef({ x: -9999, y: -9999 })
  const lookRef = useRef<{ x: number; y: number } | null>(null)
  const flyTargetRef = useRef({ x: 0, y: 0 })
  const flightProxy = useRef({ x: 0, y: 0 })
  const velocityRef = useRef({ x: 0, y: 0 })
  const scaleRef = useRef(1)
  const peekUntilRef = useRef(0)
  const focusedRef = useRef<string | null>(null)
  const isMobileRef = useRef(false)
  const flapRef = useRef<gsap.core.Timeline | null>(null)
  const featherRef = useRef<gsap.core.Timeline | null>(null)
  const quickRef = useRef<{
    headRot?: (v: number) => void
    headX?: (v: number) => void
    headY?: (v: number) => void
    pupilX?: (v: number) => void
    pupilY?: (v: number) => void
    bank?: (v: number) => void
  }>({})

  const [formData, setFormData] = useState<FormDataType>({
    fullName: "",
    email: "",
    phone: "",
    countryCode: "+1",
    gender: "",
    dob: "",
    guardianName: "",
    guardianPhone: "",
    country: "",
    province: "",
    program: "O-Level",
    subjects: ["Maths", "Computer Science"],
    schoolRegion: "",
    schoolType: "",
    grade: "",
    section: "",
    password: "",
    confirmPassword: "",
    terms: false,
    captcha: "",
  })

  /* ─────────────────── Mascot flight controller ─────────────────── */
  useEffect(() => {
    const fly = birdFlyRef.current
    const bob = birdBobRef.current
    const bank = birdBankRef.current
    const react = birdReactRef.current
    if (!fly || !bob || !bank || !react) return

    /* ---- responsive sizing ---- */
    const sizeFor = (w: number) =>
      w < 380 ? 0.3 : w < 520 ? 0.36 : w < 768 ? 0.42 : w < 1024 ? 0.5 : w < 1280 ? 0.62 : w < 1600 ? 0.74 : 0.82

    const applyScale = () => {
      scaleRef.current = sizeFor(window.innerWidth)
      isMobileRef.current = window.innerWidth < 1024
      setBirdScale(scaleRef.current)
    }
    applyScale()

    const pad = () => 128 * scaleRef.current + 8

    const parkSpot = () => {
      const w = window.innerWidth
      const p = pad()
      if (w < 1024) return { x: w - p, y: 84 }
      const card = formContainerRef.current?.getBoundingClientRect()
      const gutter = card ? w - card.right : w * 0.18
      const x = gutter > p * 1.5 ? w - p : Math.min(w - p, (card?.right ?? w * 0.7) + 16)
      const y = Math.max(150, Math.min(window.innerHeight - p, (card?.top ?? 120) + 158))
      return { x, y }
    }

    /* ---- flight state ---- */
    const start = parkSpot()
    const pos = { x: start.x, y: start.y }
    const vel = { x: 0, y: 0 }
    flightProxy.current = pos
    velocityRef.current = vel
    pointerRef.current = { x: window.innerWidth * 0.6, y: window.innerHeight * 0.36 }
    lookRef.current = { ...pointerRef.current }
    let lastPointerAt = 0
    let hasPointer = false
    let clock = 0
    let fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches
    gsap.set(fly, { x: pos.x, y: pos.y })

    /* ---- face quick tweeners (cursor tracking) ---- */
    quickRef.current = {
      headRot: gsap.quickTo(headRef.current, "rotation", { duration: 0.32, ease: "power2.out", svgOrigin: "130 90" }),
      headX: gsap.quickTo(headRef.current, "x", { duration: 0.4, ease: "power2.out" }),
      headY: gsap.quickTo(headRef.current, "y", { duration: 0.4, ease: "power2.out" }),
      pupilX: gsap.quickTo([pupilLeftRef.current, pupilRightRef.current], "x", { duration: 0.16, ease: "power2.out" }),
      pupilY: gsap.quickTo([pupilLeftRef.current, pupilRightRef.current], "y", { duration: 0.16, ease: "power2.out" }),
      bank: gsap.quickTo(bank, "rotation", { duration: 0.5, ease: "power2.out" }),
    }

    /* ---- idle life: hover bob, breathing, flapping, feet ---- */
    const breathe = gsap.timeline({ repeat: -1, defaults: { ease: "sine.inOut" } })
    breathe
      .to(bob, { y: -11, duration: 1.15 }, 0)
      .to(bob, { scaleY: 1.025, scaleX: 0.985, duration: 1.15 }, 0)
      .to(bob, { y: 0, duration: 1.15 }, 1.15)
      .to(bob, { scaleY: 0.985, scaleX: 1.012, duration: 1.15 }, 1.15)

    const flap = gsap.timeline({ repeat: -1, defaults: { ease: "sine.inOut" } })
    flap
      .to(wingLeftRef.current, { rotation: 31, y: -6, duration: 0.23, svgOrigin: "80 132" })
      .to(wingRightRef.current, { rotation: -31, y: -6, duration: 0.23, svgOrigin: "182 132" }, "<")
      .to(wingLeftRef.current, { rotation: -7, y: 4, duration: 0.27 })
      .to(wingRightRef.current, { rotation: 7, y: 4, duration: 0.27 }, "<")
    flapRef.current = flap

    /* ── every feather is hinged: primaries ripple, tail sways, crest springs ── */
    const featherL = Array.from(fly.querySelectorAll<SVGGElement>('[data-feather="left"]'))
    const featherR = Array.from(fly.querySelectorAll<SVGGElement>('[data-feather="right"]'))
    const tails = Array.from(fly.querySelectorAll<SVGGElement>("[data-tail]"))
    const crests = Array.from(fly.querySelectorAll<SVGGElement>("[data-crest]"))

    const feathers = gsap.timeline({ repeat: -1, yoyo: true, defaults: { ease: "sine.inOut" } })
    if (featherL.length) {
      feathers.to(featherL, { rotation: 15, duration: 0.3, stagger: { each: 0.055, from: "end" }, svgOrigin: "78 148" }, 0)
    }
    if (featherR.length) {
      feathers.to(featherR, { rotation: -15, duration: 0.3, stagger: { each: 0.055, from: "end" }, svgOrigin: "182 148" }, 0)
    }
    if (tails.length) {
      feathers.to(tails, { rotation: -7, x: -2, duration: 0.42, stagger: { each: 0.06, from: "start" }, svgOrigin: "96 180" }, 0)
    }
    if (crests.length) {
      feathers.to(crests, { rotation: -5, y: -1.5, duration: 0.34, stagger: { each: 0.05 }, svgOrigin: "130 46" }, 0.05)
    }
    featherRef.current = feathers

    /* occasional feather ruffle while hovering */
    const ruffle = () => {
      if (!featherL.length) return
      gsap.timeline()
        .to([...featherL, ...featherR], { rotation: (i: number) => (i % 2 ? 9 : -9), duration: 0.09, stagger: { each: 0.018, from: "random" }, ease: "power1.inOut" })
        .to([...featherL, ...featherR], { rotation: 0, duration: 0.3, stagger: { each: 0.02, from: "random" }, ease: "power2.out" })
      gsap.fromTo(tails, { rotation: 0 }, { rotation: (i: number) => (i - 1) * 6, duration: 0.16, yoyo: true, repeat: 1, ease: "sine.inOut" })
    }
    const ruffleTimer = window.setInterval(ruffle, 7000)
    window.setTimeout(ruffle, 2600)

    gsap.to(footLeftRef.current, { rotation: 9, duration: 1.15, yoyo: true, repeat: -1, ease: "sine.inOut", svgOrigin: "114 206" })
    gsap.to(footRightRef.current, { rotation: -9, duration: 1.15, yoyo: true, repeat: -1, ease: "sine.inOut", svgOrigin: "154 206", delay: 0.35 })

    /* ---- flight trail ---- */
    const dots = trailRef.current ? (Array.from(trailRef.current.children) as HTMLElement[]) : []
    const trailPts = dots.map(() => ({ x: pos.x, y: pos.y }))

    /* ---- pointer input (works over the whole page) ---- */
    const readPointer = (x: number, y: number) => {
      pointerRef.current = { x, y }
      lookRef.current = { x, y }
      lastPointerAt = performance.now()
      hasPointer = true
    }
    const onMouse = (e: MouseEvent) => { fine = true; readPointer(e.clientX, e.clientY) }
    const onTouch = (e: TouchEvent) => {
      const t = e.touches[0]
      if (!t) return
      fine = false
      readPointer(t.clientX, t.clientY)
    }
    window.addEventListener("mousemove", onMouse, { passive: true })
    window.addEventListener("touchmove", onTouch, { passive: true })
    window.addEventListener("touchstart", onTouch, { passive: true })

    /* ---- point beside the focused input, looking down at it ---- */
    const peekSpot = () => {
      const el = focusElRef.current
      if (!el) return null
      const r = el.getBoundingClientRect()
      const w = window.innerWidth
      const p = pad()
      const off = 66 + 128 * scaleRef.current * 0.5
      const roomRight = w - r.right
      const roomLeft = r.left
      let x: number
      let y = r.top - 20
      if (roomRight > off) x = r.right + off
      else if (roomLeft > off) x = r.left - off
      else {
        x = r.left + r.width / 2
        y = r.top - 44 - 128 * scaleRef.current * 0.42
      }
      return { x: clamp(x, p, w - p), y: clamp(y, Math.max(80, p * 0.7), window.innerHeight - p) }
    }

    /* ---- master loop ---- */
    const tick = () => {
      const dt = Math.min(gsap.ticker.deltaRatio(60), 2.4)
      clock += dt / 60
      const now = performance.now()
      const p = pad()
      const peek = peekSpot()
      const focused = !!focusedRef.current
      /* mobile keeps the bird parked in the header layer so it never covers inputs */
      const peeking = peek !== null && focused && fine && now < peekUntilRef.current

      /* choose the flight target */
      let target: { x: number; y: number }
      if (peeking) {
        target = peek
      } else if (fine && hasPointer) {
        /* orbit just above the pointer, flipping near the edges */
        const offX = 70 + 30 * scaleRef.current
        const offY = -(72 * scaleRef.current + 30)
        let tx = pointerRef.current.x + offX
        let ty = pointerRef.current.y + offY
        if (tx + p > window.innerWidth) tx = pointerRef.current.x - offX
        if (ty - p * 0.7 < 68) ty = pointerRef.current.y + Math.abs(offY) + 58
        target = {
          x: tx + Math.sin(clock * 1.3) * 9,
          y: ty + Math.cos(clock * 1.05) * 7,
        }
        /* gentle drifting when the cursor rests */
        if (now - lastPointerAt > 5000) {
          target.x += Math.sin(clock * 0.33) * 36
          target.y += Math.cos(clock * 0.27) * 24
        }
      } else {
        target = parkSpot()
      }
      target.x = clamp(target.x, p, window.innerWidth - p)
      target.y = clamp(target.y, Math.max(76, p * 0.7), window.innerHeight - p)
      flyTargetRef.current = target

      /* time-corrected eased follow — snappy, never laggy, still organic */
      const ease = 1 - Math.pow(0.84, dt)
      const prevX = pos.x
      const prevY = pos.y
      pos.x += (target.x - pos.x) * ease
      pos.y += (target.y - pos.y) * ease
      vel.x = (pos.x - prevX) / dt
      vel.y = (pos.y - prevY) / dt
      gsap.set(fly, { x: pos.x, y: pos.y })

      const speed = Math.hypot(vel.x, vel.y)
      /* wings and feathers beat faster the quicker the bird flies */
      flapRef.current?.timeScale(clamp(0.95 + speed * 0.26, 0.95, 2.7))
      featherRef.current?.timeScale(clamp(0.85 + speed * 0.3, 0.85, 2.8))

      /* comet trail */
      dots.forEach((dot, i) => {
        const pt = trailPts[i]
        const f = 0.36 - i * 0.038
        pt.x += (pos.x - pt.x) * f * dt
        pt.y += (pos.y - pt.y) * f * dt
        const vis = clamp((speed - 0.4) / 5, 0, 1) * (1 - i * 0.09)
        gsap.set(dot, { x: pt.x - pos.x, y: pt.y - pos.y, opacity: vis * 0.55, scale: 1 - i * 0.09 })
      })

      /* ── eyes + head aim exactly at the pointer / active field ── */
      let aim = pointerRef.current
      if (peeking && focusElRef.current) {
        const r = focusElRef.current.getBoundingClientRect()
        aim = { x: r.left + r.width / 2, y: r.top + r.height / 2 }
      }
      const headX = pos.x
      const headY = pos.y - 34 * scaleRef.current
      const reach = 250 * Math.max(scaleRef.current, 0.45)
      const nx = clamp((aim.x - headX) / reach, -1, 1)
      const ny = clamp((aim.y - headY) / reach, -1, 1)
      quickRef.current.headRot?.(nx * 19 + clamp(vel.x * 0.35, -5, 5))
      quickRef.current.headX?.(nx * 4.5)
      quickRef.current.headY?.(ny * 6)
      quickRef.current.pupilX?.(nx * 7)
      quickRef.current.pupilY?.(ny * 5.5)
      quickRef.current.bank?.(clamp(vel.x * 0.9, -18, 18))
    }
    gsap.ticker.add(tick)

    const onResize = () => {
      applyScale()
      flyTargetRef.current = parkSpot()
    }
    window.addEventListener("resize", onResize)

    return () => {
      window.removeEventListener("resize", onResize)
      window.removeEventListener("mousemove", onMouse)
      window.removeEventListener("touchmove", onTouch)
      window.removeEventListener("touchstart", onTouch)
      window.clearInterval(ruffleTimer)
      gsap.ticker.remove(tick)
      breathe.kill()
      flap.kill()
      feathers.kill()
      gsap.killTweensOf([footLeftRef.current, footRightRef.current].filter(Boolean))
    }
  }, [])

  /* natural blinking — eyelids squash shut, sometimes twice */
  useEffect(() => {
    const blink = () => {
      const l = eyeLeftRef.current
      const r = eyeRightRef.current
      if (!l || !r) return
      const dur = 0.085
      gsap.to(l, { scaleY: 0.06, duration: dur, svgOrigin: "112 86", yoyo: true, repeat: 1, ease: "power2.inOut" })
      gsap.to(r, { scaleY: 0.06, duration: dur, svgOrigin: "150 86", yoyo: true, repeat: 1, ease: "power2.inOut" })
    }
    const id = setInterval(() => {
      blink()
      if (Math.random() > 0.6) setTimeout(blink, 230)
    }, 2400 + Math.random() * 1700)
    return () => clearInterval(id)
  }, [])

  /* progress bar */
  useEffect(() => {
    if (progressRef.current) {
      gsap.to(progressRef.current, { width: `${(step / 5) * 100}%`, duration: 0.6, ease: "power3.out" })
    }
    if (step === 5) {
      setShowSuccessConfetti(true)
      setTimeout(() => setShowSuccessConfetti(false), 5000)
    }
  }, [step])

  /* focus a field → the bird swoops over to peek at it for a moment */
  useEffect(() => {
    focusedRef.current = focusedField
    if (focusedField && focusElRef.current) {
      peekUntilRef.current = performance.now() + 2600
      /* curious brow raise while peeking */
      gsap.to([browLeftRef.current, browRightRef.current], { y: -3, rotation: -4, duration: 0.35, ease: "power2.out", transformOrigin: "center" })
      if (birdReactRef.current) {
        const r = birdReactRef.current
        gsap.killTweensOf(r)
        gsap.fromTo(r, { scale: 1 }, { scale: 1.09, duration: 0.16, yoyo: true, repeat: 1, ease: "power2.out", onComplete: () => gsap.set(r, { scale: 1 }) })
      }
    } else {
      gsap.to([browLeftRef.current, browRightRef.current], { y: 0, rotation: 0, duration: 0.35, ease: "power2.out" })
    }
  }, [focusedField])

  /* ────────────────────────── Form helpers ────────────────────────── */
  const animateStepChange = (next: number) => {
    if (!formContainerRef.current) {
      setStep(next)
      return
    }
    gsap.to(formContainerRef.current, {
      x: next > step ? -40 : 40,
      opacity: 0,
      duration: 0.25,
      ease: "power2.in",
      onComplete: () => {
        setStep(next)
        gsap.fromTo(
          formContainerRef.current,
          { x: next > step ? 40 : -40, opacity: 0 },
          { x: 0, opacity: 1, duration: 0.35, ease: "power3.out" },
        )
      },
    })
    chirp(next === 5 ? "Application sent! 🎉" : next === 2 ? "Nice! Next stop, guardian details ✨" : next === 3 ? "Almost there — pick your path! 📚" : "Last step, let's lock it in 🔐")
  }

  const validateStep = (s: number): boolean => {
    const e: Record<string, string> = {}
    if (s === 1) {
      if (!formData.fullName.trim()) e.fullName = "Required"
      if (!formData.email.trim() || !/\S+@\S+\.\S+/.test(formData.email)) e.email = "Valid email required"
      if (!formData.gender) e.gender = "Required"
      if (!formData.dob) e.dob = "Required"
    }
    if (s === 2) {
      if (!formData.guardianName.trim()) e.guardianName = "Required"
      if (!formData.guardianPhone.trim()) e.guardianPhone = "Required"
      if (!formData.country) e.country = "Required"
      if (!formData.province) e.province = "Required"
    }
    if (s === 3) {
      if (!formData.schoolRegion.trim()) e.schoolRegion = "Required"
      if (!formData.schoolType) e.schoolType = "Required"
      if (!formData.grade) e.grade = "Required"
      if (!formData.program) e.program = "Required"
      if (formData.subjects.length === 0) e.subjects = "Pick at least one"
    }
    if (s === 4) {
      if (formData.password.length < 8) e.password = "Min 8 chars"
      if (formData.password !== formData.confirmPassword) e.confirmPassword = "Passwords must match"
      if (!formData.terms) e.terms = "Must accept"
      if (formData.captcha.trim() !== String(captchaA + captchaB)) e.captcha = "Incorrect"
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  /* ────────────────────────── Real submission ──────────────────────────
     The wizard used to stop at a cosmetic success screen. It now posts to the
     academy's own admissions endpoint, which creates an isolated "pending"
     student and starts a session so /admission/status can show the timeline. */
  const submitApplication = async () => {
    if (!validateStep(4)) {
      const l = browLeftRef.current
      const r = browRightRef.current
      if (l && r) gsap.fromTo([l, r], { y: 1, rotation: 0 }, { y: 4, rotation: 6, duration: 0.09, repeat: 4, yoyo: true, ease: "power1.inOut" })
      if (chirpRef.current) gsap.fromTo(chirpRef.current, { x: -9 }, { x: 9, duration: 0.06, repeat: 6, yoyo: true, ease: "power1.inOut", onComplete: () => gsap.set(chirpRef.current, { x: 0 }) })
      setChirpText("Check the highlighted fields \u{1F624}")
      setTimeout(() => setChirpText(null), 1900)
      return
    }
    if (submitting) return
    setSubmitting(true)
    setSubmitError(null)
    setChirpText("Sending your application\u2026 \u{1F680}")
    const body = new FormData()
    body.append("csrf_token", CSRF)
    body.append("full_name", formData.fullName.trim())
    body.append("email", formData.email.trim())
    body.append("phone", (formData.countryCode + " " + formData.phone).trim())
    body.append("grade", formData.grade)
    /* Send every chosen subject; the wizard allows more than one. The first
       is repeated in "subject" so older servers keep working unchanged. */
    for (const subject of formData.subjects) body.append("subjects", subject)
    body.append("subject", formData.subjects[0] || "Maths")
    body.append("guardian_name", formData.guardianName.trim())
    body.append("guardian_phone", formData.guardianPhone.trim())
    body.append("password", formData.password)
    body.append("confirm_password", formData.confirmPassword)
    body.append("terms", formData.terms ? "yes" : "")
    try {
      const res = await fetch("/admission/register", {
        method: "POST",
        body,
        headers: { Accept: "text/html" },
        redirect: "follow",
        credentials: "same-origin",
      })
      if (res.redirected && /\/admission\/status/.test(res.url)) {
        setChirpText("Application sent! \u{1F389}")
        animateStepChange(5)
        window.setTimeout(() => { window.location.href = res.url }, 2400)
        return
      }
      setSubmitError("We could not submit your application right now. Registration may be closed, or the academy office may need to check your details.")
      setChirpText("Hmm, that did not go through \u{1F615}")
      const l = browLeftRef.current
      const r = browRightRef.current
      if (l && r) gsap.fromTo([l, r], { y: 1, rotation: 0 }, { y: 4, rotation: 6, duration: 0.09, repeat: 4, yoyo: true, ease: "power1.inOut" })
    } catch {
      setSubmitError("Network problem \u2014 please check your connection and try again.")
      setChirpText("No connection \u{1F615}")
    } finally {
      setSubmitting(false)
      setTimeout(() => setChirpText(null), 2600)
    }
  }

  const handleContinue = () => {
    if (step === 4) {
      submitApplication()
      return
    }
    if (validateStep(step)) animateStepChange(step + 1)
    else {
      /* fierce face + rapid head-shake */
      const l = browLeftRef.current
      const r = browRightRef.current
      if (l && r) {
        gsap.fromTo([l, r], { y: 1, rotation: 0 }, { y: 4, rotation: 6, duration: 0.09, repeat: 4, yoyo: true, ease: "power1.inOut" })
        gsap.to([l, r], { y: 0, rotation: 0, duration: 0.3, delay: 0.55 })
      }
      if (chirpRef.current) {
        gsap.fromTo(chirpRef.current, { x: -9 }, { x: 9, duration: 0.06, repeat: 6, yoyo: true, ease: "power1.inOut", onComplete: () => gsap.set(chirpRef.current, { x: 0 }) })
      }
      setChirpText("Hey! Fix those fields 😤")
      setTimeout(() => setChirpText(null), 1900)
    }
  }

  const chirp = (text?: string) => {
    setChirpText(text ?? "Chirp! Let's go! 🐤")
    const wrap = chirpRef.current
    if (wrap) {
      gsap.killTweensOf(wrap)
      gsap.timeline({ onComplete: () => gsap.set(wrap, { rotation: 0, y: 0, scale: 1 } ) })
        .to(wrap, { y: -34, scale: 1.07, duration: 0.16, ease: "power2.out" })
        .to(wrap, { rotation: 380, duration: 0.7, ease: "power2.inOut" }, "<")
        .to(wrap, { scaleY: 0.84, scaleX: 1.14, duration: 0.12, ease: "power2.out" }, "-=0.18")
        .to(wrap, { scaleY: 1, scaleX: 1, y: 0, duration: 0.3, ease: "elastic.out(1,0.45)" })
    }
    /* happy brows + open beak + "chirp" */
    const l = browLeftRef.current
    const r = browRightRef.current
    if (l && r) {
      gsap.to([l, r], { y: -5, duration: 0.22, ease: "power2.out" })
      gsap.to([l, r], { y: 0, duration: 0.3, delay: 0.95, ease: "power2.out" })
    }
    if (beakLowerRef.current) {
      gsap.timeline()
        .to(beakLowerRef.current, { y: 6, rotation: 8, duration: 0.1, ease: "power2.out", svgOrigin: "130 116" })
        .to(beakLowerRef.current, { y: 2, rotation: 3, duration: 0.08, yoyo: true, repeat: 1 })
        .to(beakLowerRef.current, { y: 0, rotation: 0, duration: 0.25, ease: "power2.inOut" })
    }
    /* sparkle burst */
    const sparks = sparksRef.current?.children
    if (sparks) {
      Array.from(sparks).forEach((s, i) => {
        const ang = (Math.PI * 2 * i) / sparks.length + Math.random() * 0.5
        const dist = 40 + Math.random() * 34
        gsap.killTweensOf(s)
        gsap.set(s, { x: 0, y: 0, scale: 0.3, opacity: 0 })
        gsap.timeline()
          .to(s, { x: Math.cos(ang) * dist, y: Math.sin(ang) * dist, scale: 1, opacity: 1, duration: 0.3, ease: "power2.out" })
          .to(s, { y: `+=16`, opacity: 0, scale: 0.4, duration: 0.55, ease: "power2.in" })
      })
    }
    setTimeout(() => setChirpText(null), 1700)
  }

  const updateField = (k: keyof FormDataType, v: any) => {
    const prev = { ...formData, [k]: v } as FormDataType
    setFormData(prev)
    if (k === "country") setFormData(p => ({ ...p, country: v, province: "" }))
    const checks: Record<string, boolean> = {
      fullName: prev.fullName.trim().length > 3,
      email: /\S+@\S+\.\S+/.test(prev.email),
      guardianName: prev.guardianName.trim().length > 2,
      guardianPhone: prev.guardianPhone.trim().length > 6,
      schoolRegion: prev.schoolRegion.trim().length > 2,
    }
    if (checks[k] && !lastValidFields.has(k)) {
      setLastValidFields(s => new Set([...s, k]))
      chirp("Nice! Field complete ✨")
    }
  }

  const selectProgram = (p: string) => {
    /* single atomic update — changing program clears the grade */
    setFormData(prev => ({ ...prev, program: p, grade: "" }))
    chirp(`${p} it is! 🎓`)
  }

  const toggleSubject = (s: string) => {
    const adding = !formData.subjects.includes(s)
    setFormData(p => ({
      ...p,
      subjects: p.subjects.includes(s) ? p.subjects.filter(x => x !== s) : [...p.subjects, s],
    }))
    if (adding) chirp(`Yay! ${s} added ✨`)
  }

  const onFieldFocus = (name: string, el: HTMLElement) => {
    setFocusedField(name)
    focusElRef.current = el
  }
  const onFieldBlur = () => {
    setFocusedField(null)
    focusElRef.current = null
  }

  /* the bird greets the user once on arrival */
  useEffect(() => {
    const t = window.setTimeout(() => chirp("Hey! I'm Red — move your cursor 👀"), 1000)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const availableStates = formData.country ? countryStateMap[formData.country] || [] : []
  const availableGrades = formData.program ? gradeOptionsByProgram[formData.program] || [] : [...gradeOptionsByProgram["O-Level"], ...gradeOptionsByProgram["A-Level"]]

  return (
    <div className="min-h-screen bg-white text-[#1A1A1A] selection:bg-[#0B7F61] selection:text-white overflow-x-hidden" style={{ fontFamily: "Inter, system-ui, sans-serif" }}>
      {/* Ambient page light (pure white base + soft premium tint) */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -top-40 -left-32 w-[520px] h-[520px] rounded-full bg-[#0B7F61]/[0.055] blur-[110px]" />
        <div className="absolute top-[30%] -right-40 w-[480px] h-[480px] rounded-full bg-[#F59E0B]/[0.06] blur-[120px]" />
        <div className="absolute bottom-0 left-1/3 w-[420px] h-[420px] rounded-full bg-[#0B7F61]/[0.04] blur-[120px]" />
      </div>

      {/* ══════ FREE-FLYING MASCOT — portalled straight into <body> so it
          floats above every card, border and the header ══════ */}
      {createPortal(
        <div
          ref={birdFlyRef}
          aria-hidden="true"
          className="fixed left-0 top-0 pointer-events-none"
          style={{ width: 0, height: 0, zIndex: 2147483000 }}
        >
          {/* speed comet trail — outside the chirp loop so it never spins */}
          <div ref={trailRef} className="absolute" style={{ left: 0, top: 0 }} aria-hidden="true">
            {["#FF6A4D", "#FFC94E", "#FF8A62", "#FFC94E", "#FF6A4D", "#FFD9A0", "#FF8A62"].map((c, i) => (
              <span
                key={i}
                className="absolute block rounded-full"
                style={{
                  width: 11 - i,
                  height: 11 - i,
                  marginLeft: -(11 - i) / 2,
                  marginTop: -(11 - i) / 2,
                  background: c,
                  boxShadow: `0 0 12px ${c}`,
                  opacity: 0,
                }}
              />
            ))}
          </div>

          <div ref={chirpRef} className="absolute" style={{ left: -BIRD / 2, top: -BIRD / 2, width: BIRD, height: BIRD }}>
            <div style={{ width: BIRD, height: BIRD, transform: `scale(${birdScale})`, transformOrigin: `${BIRD / 2}px ${BIRD / 2}px` }}>
              <div ref={birdBobRef} className="relative w-full h-full" style={{ transformOrigin: "50% 88%" }}>
                <div ref={birdReactRef} className="w-full h-full" style={{ transformOrigin: "50% 55%" }}>
                  <div ref={birdBankRef} className="w-full h-full" style={{ transformOrigin: "50% 62%" }}>
                    <BirdMascot
                      headRef={headRef}
                      eyeLeftRef={eyeLeftRef}
                      eyeRightRef={eyeRightRef}
                      pupilLeftRef={pupilLeftRef}
                      pupilRightRef={pupilRightRef}
                      browLeftRef={browLeftRef}
                      browRightRef={browRightRef}
                      beakLowerRef={beakLowerRef}
                      wingLeftRef={wingLeftRef}
                      wingRightRef={wingRightRef}
                      footLeftRef={footLeftRef}
                      footRightRef={footRightRef}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* celebratory sparkle burst */}
            <div ref={sparksRef} className="absolute" style={{ left: 0, top: 0 }} aria-hidden="true">
              {["#FFC94E", "#FF6A4D", "#7ED957", "#FFFFFF", "#FFC94E", "#FF6A4D", "#7ED957", "#FFFFFF"].map((c, i) => (
                <span
                  key={i}
                  className="absolute block rounded-full"
                  style={{
                    width: i % 2 ? 7 : 10,
                    height: i % 2 ? 7 : 10,
                    marginLeft: i % 2 ? -3.5 : -5,
                    marginTop: i % 2 ? -3.5 : -5,
                    background: c,
                    boxShadow: `0 0 10px ${c}`,
                    opacity: 0,
                  }}
                />
              ))}
            </div>

            {chirpText && (
              <div className="absolute" style={{ left: BIRD / 2, top: (BIRD / 2) * (1 - birdScale) + 2 }}>
                <div className="relative -translate-x-1/2 -translate-y-full max-sm:-translate-x-[58%]">
                  <div className="bg-[#1A1A1A] text-white text-[11px] sm:text-[12px] font-black px-3.5 py-2 rounded-2xl shadow-2xl flex items-center gap-2 max-w-[220px] sm:max-w-none sm:whitespace-nowrap">
                    <span className="w-2 h-2 shrink-0 bg-[#FF6A4D] rounded-full animate-pulse" />
                    {chirpText}
                  </div>
                  <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2.5 h-2.5 bg-[#1A1A1A] rotate-45 rounded-[2px]" />
                </div>
              </div>
            )}
          </div>
        </div>,
        document.body,
      )}

      {/* Top Nav */}
      <header className="sticky top-0 z-30 bg-white/85 backdrop-blur-md border-b border-black/[0.06]">
        <div className="mx-auto max-w-[1280px] px-4 sm:px-6 lg:px-8 h-[64px] flex items-center justify-between">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-[#0B7F61] flex items-center justify-center text-white font-black text-[16px] tracking-tighter shadow-[0_6px_16px_rgba(11,127,97,0.28)]">{APP_NAME.charAt(0)}</div>
              <span className="font-extrabold text-[18px] tracking-tight" style={{ fontFamily: "var(--font-display)" }}>{APP_NAME}</span>
              <span className="hidden sm:inline text-[11px] font-bold tracking-widest text-black/40 ml-1">ACADEMY</span>
            </div>
            <nav className="hidden lg:flex items-center gap-6 text-[13px] font-semibold text-black/60">
              <a href="/register" className="text-black" aria-current="page">Join</a>
              <a href="/explore" className="hover:text-black">Explore</a>
              <a href="/about" className="hover:text-black">About</a>
              <a href="/privacy" className="hover:text-black">Privacy</a>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 text-[12px] font-semibold text-black/60">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Admissions open — O & A Levels
            </div>
            <a href="/login" className="hidden sm:inline-flex px-4 py-2 rounded-full border border-black/10 text-[13px] font-bold hover:bg-black/[0.03] transition">Sign in</a>
            <a href="/" className="px-4 py-2 rounded-full bg-[#0B7F61] text-white text-[13px] font-bold shadow-[0_8px_20px_rgba(11,127,97,0.25)] hover:bg-[#066B53] transition">Home</a>
          </div>
        </div>
        <div className="h-[3px] bg-black/[0.06] w-full">
          <div ref={progressRef} className="h-full bg-[#0B7F61] w-[20%]" />
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-[860px] px-4 sm:px-6 py-8 sm:py-12">
        {step !== 5 ? (
          <div>
            {/* Form Card */}
            <div className="bg-white rounded-[24px] shadow-[0_24px_70px_rgba(0,0,0,0.09)] border border-black/[0.07] overflow-hidden">
              <div className="px-6 sm:px-8 pt-6 sm:pt-8 pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-full bg-[#FFF0F0] border border-[#0B7F61]/20 text-[#0B7F61] text-[11px] font-extrabold tracking-widest">STEP {step} OF 4</span>
                    <span className="hidden sm:inline text-[12px] font-semibold text-black/40">• {step === 3 ? "O/A Levels only" : "Registration"}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {[1, 2, 3, 4].map(i => (
                      <div key={i} className={`h-1.5 rounded-full transition-all duration-500 ${i === step ? "w-8 bg-[#0B7F61]" : i < step ? "w-6 bg-[#0B7F61]/60" : "w-6 bg-black/10"}`} />
                    ))}
                  </div>
                </div>
              </div>

              <div ref={formContainerRef} className="px-6 sm:px-8 pb-8">
                {step === 1 && (
                  <div className="pt-4">
                    <h1 className="text-[28px] sm:text-[32px] font-extrabold tracking-tight leading-none" style={{ fontFamily: "var(--font-display)" }}>
                      Create your <span className="text-[#0B7F61]">profile</span>
                    </h1>
                    <p className="text-[13.5px] text-black/60 font-medium mt-2">Tell us about yourself — our bird will peek when you type! 🐦</p>

                    <div className="mt-7 space-y-4">
                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">FULL NAME *</label>
                        <div className={`mt-1.5 relative flex items-center border-2 rounded-xl px-3 py-2.5 bg-white transition-all ${focusedField === "fullName" ? "border-[#0B7F61] shadow-[0_0_0_4px_rgba(11,127,97,0.08)]" : errors.fullName ? "border-red-400" : "border-black/10"}`}>
                          <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3 text-black/60">◉</span>
                          <input onFocus={e => onFieldFocus("fullName", e.currentTarget)} onBlur={onFieldBlur} value={formData.fullName} onChange={e => updateField("fullName", e.target.value)} placeholder="Alex Morgan" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                        </div>
                        {errors.fullName && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.fullName}</p>}
                      </div>

                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">EMAIL ADDRESS *</label>
                        <div className={`mt-1.5 relative flex items-center border-2 rounded-xl px-3 py-2.5 bg-white transition-all ${focusedField === "email" ? "border-[#0B7F61] shadow-[0_0_0_4px_rgba(11,127,97,0.08)]" : errors.email ? "border-red-400" : "border-black/10"}`}>
                          <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3 text-black/60">✉</span>
                          <input onFocus={e => onFieldFocus("email", e.currentTarget)} onBlur={onFieldBlur} value={formData.email} onChange={e => updateField("email", e.target.value)} placeholder="alex@email.com" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" type="email" />
                        </div>
                        {errors.email && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.email}</p>}
                      </div>

                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">PHONE NUMBER (OPTIONAL)</label>
                        <div className={`mt-1.5 flex items-center border-2 rounded-xl bg-white overflow-hidden transition-all ${focusedField === "phone" ? "border-[#0B7F61] shadow-[0_0_0_4px_rgba(11,127,97,0.08)]" : "border-black/10"}`}>
                          <select value={formData.countryCode} onChange={e => updateField("countryCode", e.target.value)} className="px-3 py-2.5 bg-black/[0.04] border-r border-black/10 text-[13px] font-bold outline-none">
                            <option>+1</option><option>+44</option><option>+91</option><option>+61</option><option>+971</option>
                          </select>
                          <input onFocus={e => onFieldFocus("phone", e.currentTarget)} onBlur={onFieldBlur} value={formData.phone} onChange={e => updateField("phone", e.target.value)} placeholder="(555) 000-0000" className="flex-1 px-3 py-2.5 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="text-[11px] font-extrabold tracking-widest text-black/60">GENDER *</label>
                          <div className={`mt-1.5 relative border-2 rounded-xl px-3 py-2.5 flex items-center justify-between bg-white ${focusedField === "gender" ? "border-[#0B7F61]" : errors.gender ? "border-red-400" : "border-black/10"}`}>
                            <select onFocus={e => onFieldFocus("gender", e.currentTarget)} onBlur={onFieldBlur} value={formData.gender} onChange={e => updateField("gender", e.target.value)} className="flex-1 bg-transparent outline-none text-[14px] font-semibold text-black/80">
                              <option value="">Select gender</option>
                              <option>Female</option><option>Male</option><option>Non-binary</option><option>Prefer not to say</option>
                            </select>
                          </div>
                          {errors.gender && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.gender}</p>}
                        </div>
                        <div>
                          <label className="text-[11px] font-extrabold tracking-widest text-black/60">DATE OF BIRTH *</label>
                          <div className={`mt-1.5 border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "dob" ? "border-[#0B7F61]" : errors.dob ? "border-red-400" : "border-black/10"}`}>
                            <input onFocus={e => onFieldFocus("dob", e.currentTarget)} onBlur={onFieldBlur} value={formData.dob} onChange={e => updateField("dob", e.target.value)} type="date" className="w-full bg-transparent outline-none text-[14px] font-semibold" />
                          </div>
                          {errors.dob && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.dob}</p>}
                        </div>
                      </div>

                      <button onClick={handleContinue} className="w-full mt-2 h-[52px] rounded-xl bg-[#0B7F61] text-white font-extrabold text-[14px] tracking-wide shadow-[0_10px_24px_rgba(11,127,97,0.3)] hover:bg-[#066B53] active:scale-[0.99] transition-all">
                        Continue →
                      </button>
                      <p className="text-center text-[11px] font-semibold text-black/40">O &amp; A Level programmes 🐦</p>
                    </div>
                  </div>
                )}

                {step === 2 && (
                  <div className="pt-4">
                    <h2 className="text-[26px] font-extrabold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>Guardian & Location</h2>
                    <p className="text-[13px] text-black/60 font-medium mt-1">Guardian details + location. State list adapts to your country ✨</p>

                    <div className="mt-6 space-y-5">
                      <div className="rounded-2xl bg-[#F1FAF6] border border-[#0B7F61]/10 p-4">
                        <div className="flex items-center gap-2">
                          <span className="w-7 h-7 rounded-full bg-[#0B7F61] text-white flex items-center justify-center text-[12px] font-black">1</span>
                          <h3 className="text-[13px] font-extrabold tracking-wide">Guardian / Parent Details</h3>
                        </div>
                        <div className="mt-4 space-y-3">
                          <div>
                            <label className="text-[11px] font-extrabold tracking-widest text-black/60">FATHER'S / GUARDIAN'S NAME *</label>
                            <div className={`mt-1.5 flex items-center border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "guardianName" ? "border-[#0B7F61]" : errors.guardianName ? "border-red-400" : "border-black/10"}`}>
                              <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3">👤</span>
                              <input onFocus={e => onFieldFocus("guardianName", e.currentTarget)} onBlur={onFieldBlur} value={formData.guardianName} onChange={e => updateField("guardianName", e.target.value)} placeholder="Sarah Johnson" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                            </div>
                            {errors.guardianName && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.guardianName}</p>}
                          </div>
                          <div>
                            <label className="text-[11px] font-extrabold tracking-widest text-black/60">GUARDIAN CONTACT NUMBER *</label>
                            <div className={`mt-1.5 flex items-center border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "guardianPhone" ? "border-[#0B7F61]" : errors.guardianPhone ? "border-red-400" : "border-black/10"}`}>
                              <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3">📞</span>
                              <input onFocus={e => onFieldFocus("guardianPhone", e.currentTarget)} onBlur={onFieldBlur} value={formData.guardianPhone} onChange={e => updateField("guardianPhone", e.target.value)} placeholder="+1 (555) 123-4567" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                            </div>
                            {errors.guardianPhone && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.guardianPhone}</p>}
                          </div>
                        </div>
                      </div>

                      <div className="rounded-2xl bg-white border border-black/10 p-4">
                        <div className="flex items-center gap-2">
                          <span className="w-7 h-7 rounded-full bg-black text-white flex items-center justify-center text-[12px] font-black">2</span>
                          <h3 className="text-[13px] font-extrabold tracking-wide">Where you're from</h3>
                          <span className="ml-auto text-[10px] font-black tracking-widest bg-[#FFF0F0] text-[#0B7F61] px-2 py-1 rounded-full">{formData.country ? `${availableStates.length} states` : "Pick country first"}</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                          <div>
                            <label className="text-[11px] font-bold text-black/60">COUNTRY *</label>
                            <select value={formData.country} onChange={e => updateField("country", e.target.value)} className={`mt-1.5 w-full border-2 rounded-xl px-3 py-2.5 bg-white text-[14px] font-semibold outline-none ${errors.country ? "border-red-400" : "border-black/10"}`}>
                              <option value="">Select country</option>
                              {Object.keys(countryStateMap).map(c => <option key={c}>{c}</option>)}
                            </select>
                            {errors.country && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.country}</p>}
                          </div>
                          <div>
                            <label className="text-[11px] font-bold text-black/60">PROVINCE / STATE *</label>
                            <select value={formData.province} onChange={e => updateField("province", e.target.value)} disabled={!formData.country} className={`mt-1.5 w-full border-2 rounded-xl px-3 py-2.5 bg-white text-[14px] font-semibold outline-none disabled:opacity-40 disabled:cursor-not-allowed ${errors.province ? "border-red-400" : "border-black/10"}`}>
                              <option value="">{formData.country ? "Select state" : "Select country first"}</option>
                              {availableStates.map(s => <option key={s}>{s}</option>)}
                            </select>
                            {errors.province && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.province}</p>}
                            {formData.country && <p className="text-[11px] text-black/40 font-medium mt-1">{availableStates.length} options for {formData.country}</p>}
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-3 pt-2">
                        <button onClick={() => animateStepChange(1)} className="px-6 h-[48px] rounded-xl border border-black/10 bg-white font-bold text-[13px]">Previous</button>
                        <button onClick={handleContinue} className="flex-1 h-[48px] rounded-xl bg-[#0B7F61] text-white font-extrabold text-[14px] shadow-[0_10px_24px_rgba(11,127,97,0.25)] hover:bg-[#066B53] transition">Continue →</button>
                      </div>
                    </div>
                  </div>
                )}

                {step === 3 && (
                  <div className="pt-4">
                    <h2 className="text-[22px] sm:text-[26px] font-extrabold tracking-tight leading-tight" style={{ fontFamily: "var(--font-display)" }}>Program, School & Subjects</h2>
                    <p className="text-[12.5px] text-black/55 font-medium mt-2 leading-relaxed">Step 2 of 3 — <span className="text-[#0B7F61] font-bold">Only O-Level & A-Level</span>. Subjects limited to <span className="font-bold">Maths & Computer Science</span>.</p>

                    <div className="mt-5">
                      <label className="text-[11px] font-extrabold tracking-widest text-black/60">PROGRAM * — Choose one</label>
                      <div className="mt-2 grid grid-cols-2 gap-3">
                        {programOptions.map(p => (
                          <button key={p} onClick={() => selectProgram(p)} type="button" className={`rounded-xl border-2 px-4 py-3 text-left transition ${formData.program === p ? "border-[#0B7F61] bg-[#FFF0F0] shadow-[0_4px_12px_rgba(11,127,97,0.12)]" : "border-black/10 bg-white hover:border-black/20"}`}>
                            <p className="text-[11px] font-black tracking-widest text-black/50">{p === "O-Level" ? "CAMBRIDGE O-LEVEL" : "CAMBRIDGE A-LEVEL"}</p>
                            <p className="text-[14px] font-extrabold mt-1">{p}</p>
                            <p className="text-[11px] font-semibold text-black/50 mt-0.5">{p === "O-Level" ? "Grades 9-11" : "AS & A2"}</p>
                          </button>
                        ))}
                      </div>
                      {errors.program && <p className="text-[11px] text-red-500 font-bold mt-2">{errors.program}</p>}
                    </div>

                    <div className="mt-4">
                      <label className="text-[11px] font-extrabold tracking-widest text-black/60">SUBJECTS — Only these two ✨</label>
                      <div className="mt-2 flex gap-2">
                        {subjectOptions.map(sub => {
                          const active = formData.subjects.includes(sub)
                          return (
                            <button key={sub} onClick={() => toggleSubject(sub)} className={`flex-1 py-2.5 rounded-full text-[13.5px] font-extrabold border-2 transition flex items-center justify-center gap-2 ${active ? "bg-[#0B7F61] text-white border-[#0B7F61] shadow-[0_6px_16px_rgba(11,127,97,0.25)]" : "bg-white text-black/50 border-black/10"}`}>
                              {active ? "✓ " : "+ "}{sub}
                            </button>
                          )
                        })}
                      </div>
                      <p className="text-[11px] font-semibold text-black/40 mt-2">No other subjects available — focused curriculum for excellence.</p>
                      {errors.subjects && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.subjects}</p>}
                    </div>

                    <div className="mt-5 p-4 rounded-2xl border border-black/10 bg-[#F7FBF9]">
                      <h4 className="text-[12px] font-extrabold tracking-widest text-black/70">WHERE YOU STUDY</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                        <div>
                          <label className="text-[11px] font-bold text-black/60">School state / region *</label>
                          <input value={formData.schoolRegion} onChange={e => updateField("schoolRegion", e.target.value)} onFocus={e => onFieldFocus("schoolRegion", e.currentTarget)} onBlur={onFieldBlur} placeholder="e.g. California" className={`mt-1.5 w-full border-2 rounded-xl px-3 py-2.5 text-[13px] font-semibold outline-none bg-white ${focusedField === "schoolRegion" ? "border-[#0B7F61]" : errors.schoolRegion ? "border-red-400" : "border-black/10"}`} />
                          {errors.schoolRegion && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.schoolRegion}</p>}
                        </div>
                        <div>
                          <label className="text-[11px] font-bold text-black/60">School type *</label>
                          <select value={formData.schoolType} onChange={e => updateField("schoolType", e.target.value)} className={`mt-1.5 w-full border-2 rounded-xl px-3 py-2.5 text-[13px] font-semibold bg-white outline-none ${errors.schoolType ? "border-red-400" : "border-black/10"}`}>
                            <option value="">Select type</option><option>Public</option><option>Private</option><option>International</option><option>Cambridge Centre</option>
                          </select>
                          {errors.schoolType && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.schoolType}</p>}
                        </div>
                      </div>

                      <h4 className="text-[12px] font-extrabold tracking-widest text-black/70 mt-4">GRADE — {formData.program} only</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                        <div>
                          <label className="text-[11px] font-bold text-black/60">Class / grade *</label>
                          <select value={formData.grade} onChange={e => updateField("grade", e.target.value)} className={`mt-1.5 w-full border-2 rounded-xl px-3 py-2.5 text-[13px] font-semibold bg-white outline-none ${errors.grade ? "border-red-400" : "border-black/10"}`}>
                            <option value="">Select grade for {formData.program}</option>
                            {availableGrades.map(g => <option key={g}>{g}</option>)}
                          </select>
                          {errors.grade && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.grade}</p>}
                        </div>
                        <div>
                          <label className="text-[11px] font-bold text-black/60">Section (optional)</label>
                          <input value={formData.section} onChange={e => updateField("section", e.target.value)} placeholder="e.g. A" className="mt-1.5 w-full border-2 border-black/10 rounded-xl px-3 py-2.5 text-[13px] font-semibold outline-none bg-white" />
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-3 mt-6">
                      <button onClick={() => animateStepChange(2)} className="px-6 h-[48px] rounded-xl border border-black/10 bg-white font-bold text-[13px]">← Previous</button>
                      <button onClick={handleContinue} className="flex-1 h-[48px] rounded-xl bg-[#0B7F61] text-white font-extrabold text-[14px] shadow-[0_10px_24px_rgba(11,127,97,0.25)]">Continue →</button>
                    </div>
                  </div>
                )}

                {step === 4 && (
                  <div className="pt-4">
                    <h2 className="text-[26px] font-extrabold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>Password & Finish</h2>
                    <p className="text-[13px] text-black/60 font-medium mt-1">Step 3 of 3 — Lock it in! The bird is on guard 🔐</p>

                    <div className="mt-6 space-y-4">
                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">PASSWORD *</label>
                        <div className={`mt-1.5 flex items-center border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "password" ? "border-[#0B7F61]" : errors.password ? "border-red-400" : "border-black/10"}`}>
                          <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3">🔒</span>
                          <input type="password" onFocus={e => onFieldFocus("password", e.currentTarget)} onBlur={onFieldBlur} value={formData.password} onChange={e => updateField("password", e.target.value)} placeholder="Create a strong password" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                        </div>
                        <p className="text-[11px] font-semibold text-black/40 mt-1">Minimum 8 characters</p>
                        {errors.password && <p className="text-[11px] text-red-500 font-bold">{errors.password}</p>}
                      </div>

                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">CONFIRM PASSWORD *</label>
                        <div className={`mt-1.5 flex items-center border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "confirmPassword" ? "border-[#0B7F61]" : errors.confirmPassword ? "border-red-400" : "border-black/10"}`}>
                          <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3">🔒</span>
                          <input type="password" onFocus={e => onFieldFocus("confirmPassword", e.currentTarget)} onBlur={onFieldBlur} value={formData.confirmPassword} onChange={e => updateField("confirmPassword", e.target.value)} placeholder="Repeat password" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                        </div>
                        <p className="text-[11px] font-semibold text-black/40 mt-1">Minimum 8 characters</p>
                        {errors.confirmPassword && <p className="text-[11px] text-red-500 font-bold">{errors.confirmPassword}</p>}
                      </div>

                      <label className="flex items-start gap-3 p-3 rounded-xl border border-black/10 bg-[#F7FBF9] cursor-pointer">
                        <input type="checkbox" checked={formData.terms} onChange={e => updateField("terms", e.target.checked)} className="mt-1 w-4 h-4 accent-[#0B7F61]" />
                        <span className="text-[12.5px] font-semibold leading-relaxed">I accept the <a className="text-[#0B7F61] underline font-bold">terms and conditions</a> and <a className="text-[#0B7F61] underline font-bold">privacy policy</a>. *</span>
                      </label>
                      {errors.terms && <p className="text-[11px] text-red-500 font-bold -mt-2">{errors.terms}</p>}

                      <div className="rounded-xl border-2 border-black/10 bg-white p-4 flex items-center justify-between gap-4">
                        <div>
                          <p className="text-[11px] font-extrabold tracking-widest text-black/60">SECURITY CHECK *</p>
                          <p className="text-[16px] font-black mt-1">{captchaA} + {captchaB} = <span className="text-[#0B7F61]">?</span></p>
                        </div>
                        <input value={formData.captcha} onChange={e => updateField("captcha", e.target.value)} placeholder="Answer" onFocus={e => onFieldFocus("captcha", e.currentTarget)} onBlur={onFieldBlur} className={`w-24 h-12 rounded-xl border-2 text-center text-[16px] font-black outline-none bg-[#F1FAF6] ${errors.captcha ? "border-red-400" : focusedField === "captcha" ? "border-[#0B7F61]" : "border-black/10"}`} />
                      </div>
                      {errors.captcha && <p className="text-[11px] text-red-500 font-bold">{errors.captcha}</p>}

                      {submitError && (
                        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[12.5px] font-semibold text-red-700">{submitError}</div>
                      )}
                      <div className="flex gap-3 pt-2">
                        <button onClick={() => animateStepChange(3)} className="px-6 h-[48px] rounded-xl border border-black/10 bg-white font-bold text-[13px]">← Previous</button>
                        <button onClick={handleContinue} disabled={submitting} className="flex-1 h-[56px] rounded-xl bg-[#0B7F61] text-white font-black text-[15px] tracking-wide shadow-[0_12px_28px_rgba(11,127,97,0.3)] hover:bg-[#066B53] transition disabled:opacity-70 disabled:cursor-not-allowed">{submitting ? "Sending\u2026" : "Get Started \u2728"}</button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <p className="text-center text-[11px] font-semibold text-black/30 mt-4">🔒 Secure sign-up • O &amp; A Level programmes</p>
          </div>
        ) : (
          <div className="relative">
            {showSuccessConfetti && (
              <div className="pointer-events-none fixed inset-0 z-50 overflow-hidden">
                {Array.from({ length: 42 }).map((_, i) => (
                  <div key={i} className="absolute w-2 h-6 rounded-full animate-bounce" style={{ left: `${Math.random() * 100}%`, top: `-10px`, background: ["#0B7F61", "#16B389", "#A3D64B", "#2F6BFF", "#FF8C00"][i % 5], animationDelay: `${Math.random() * 1.2}s`, animationDuration: `${1 + Math.random()}s`, transform: `rotate(${Math.random() * 360}deg)` }} />
                ))}
              </div>
            )}
            <div className="bg-white rounded-[28px] border border-black/[0.06] shadow-[0_24px_80px_rgba(0,0,0,0.10)] overflow-hidden">
              <div className="bg-gradient-to-r from-[#0B7F61] to-[#E11D48] px-6 sm:px-10 py-8 text-white relative overflow-hidden">
                <div className="absolute top-0 right-0 w-72 h-72 bg-white/10 rounded-full blur-3xl -translate-y-20 translate-x-20" />
                <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                  <div>
                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/15 border border-white/20 text-[11px] font-extrabold tracking-widest">APPLICATION STATUS • O/A LEVELS</span>
                    <h1 className="text-[28px] sm:text-[34px] font-black tracking-tight mt-3">Application status</h1>
                    <p className="text-white/90 text-[15px] font-semibold mt-1">Received, {formData.fullName || "Alex"} . 🎉</p>
                    <p className="text-white/70 text-[13px] font-medium mt-2 max-w-xl">Your registration is with our admissions team. Most accounts are approved within 24 hours.</p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="w-20 h-20 rounded-3xl bg-white flex items-center justify-center text-3xl shadow-xl animate-bounce">🐤🎊</div>
                    <div className="hidden sm:block text-right">
                      <p className="text-white/70 text-[11px] font-bold tracking-widest">APPLICANT</p>
                      <p className="text-white font-black">{formData.fullName || "Alex Morgan"}</p>
                      <p className="text-white/80 text-[12px] font-semibold">{formData.email || "alex@email.com"} • {formData.program} • {formData.grade}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid lg:grid-cols-[1.2fr_0.8fr] gap-8 p-6 sm:p-10">
                <div>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#0B7F61] text-white flex items-center justify-center font-black text-[12px]">✓</div>
                    <h3 className="font-extrabold text-[16px]">Timeline</h3>
                    <span className="ml-auto px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-[11px] font-black">O/A PIPELINE</span>
                  </div>
                  <div className="mt-6 relative">
                    <div className="absolute left-[18px] top-8 bottom-8 w-[2px] bg-black/10" />
                    <div className="absolute left-[18px] top-8 h-16 w-[2px] bg-emerald-500" />
                    <div className="flex gap-4">
                      <div className="w-9 h-9 rounded-full bg-emerald-500 border-4 border-emerald-100 flex items-center justify-center text-white text-[14px] shrink-0 z-10">✓</div>
                      <div className="flex-1 bg-[#F0FDF4] border border-emerald-200 rounded-2xl p-4">
                        <div className="flex items-center justify-between">
                          <p className="font-extrabold text-[14px]">Registration submitted</p>
                          <span className="px-2.5 py-1 rounded-full bg-white border border-emerald-200 text-[11px] font-bold text-emerald-700">7 November 2026</span>
                        </div>
                        <p className="text-[12.5px] font-medium text-black/60 mt-1">We’ve received: {formData.program} • {(formData.subjects || []).join(" & ")} • {formData.grade || "No grade yet"}</p>
                      </div>
                    </div>
                    <div className="flex gap-4 mt-5">
                      <div className="w-9 h-9 rounded-full bg-amber-400 border-4 border-amber-100 flex items-center justify-center text-white shrink-0 z-10 animate-pulse">●</div>
                      <div className="flex-1 bg-[#FFFBEB] border border-amber-200 rounded-2xl p-4">
                        <p className="font-extrabold text-[14px]">Under review</p>
                        <p className="text-[12.5px] font-medium text-black/60 mt-1">Nothing to do for now. We will email you when your account is approved.</p>
                        <div className="mt-3 flex items-center gap-2 text-[11px] font-bold text-amber-700">
                          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" /> Our bird is cheering • Est. 24h
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="mt-8 flex gap-3">
                    <a href="/admission/status" className="flex-1 h-11 rounded-xl bg-[#0B7F61] text-white font-bold text-[13px] inline-flex items-center justify-center hover:bg-[#066B53] transition">View my application status →</a>
                    <button onClick={() => setStep(1)} className="px-5 h-11 rounded-xl border border-black/10 bg-white font-bold text-[13px]">Start another application</button>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="rounded-2xl border border-black/10 p-5 bg-[#F7FBF9]">
                    <h4 className="font-extrabold text-[13px]">What happens next?</h4>
                    <ul className="mt-3 space-y-2.5 text-[13px] font-medium text-black/70">
                      <li className="flex gap-2"><span className="text-[#0B7F61] font-black">1.</span> Admissions reviews your O/A Level profile</li>
                      <li className="flex gap-2"><span className="text-[#0B7F61] font-black">2.</span> You’ll get an email + SMS when approved</li>
                      <li className="flex gap-2"><span className="text-[#0B7F61] font-black">3.</span> Log in to access your focused Maths & CS track</li>
                    </ul>
                  </div>
                  <div className="rounded-[20px] bg-gradient-to-br from-[#ECF8F2] to-[#F3FBF6] border border-black/10 p-6 flex flex-col items-center text-center relative overflow-hidden">
                    <div className="absolute -top-6 -right-6 w-24 h-24 bg-[#0B7F61]/10 rounded-full blur-2xl" />
                    <div className="w-20 h-20 rounded-3xl bg-white border-2 border-black/5 shadow flex items-center justify-center text-3xl animate-bounce">🐤🎉</div>
                    <p className="font-black text-[15px] mt-3">Our bird is celebrating! 🎊</p>
                    <p className="text-[12px] font-semibold text-black/50 mt-1">Doing loop-de-loops — confetti everywhere!</p>
                    <div className="mt-4 w-full h-2 bg-black/5 rounded-full overflow-hidden">
                      <div className="h-full w-[68%] bg-[#0B7F61] rounded-full" />
                    </div>
                    <p className="text-[11px] font-bold text-black/40 mt-2">68% of O/A students approved in under 12h</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="relative z-10 border-t border-black/5 bg-white/70 backdrop-blur mt-8">
        <div className="mx-auto max-w-[1280px] px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-bold tracking-widest text-black/30">
          <span>© 2026 EDUPATH ACADEMY • O & A LEVELS</span>
          <span className="flex items-center gap-3"><span>Privacy</span> <span>Terms</span> <span>Support</span></span>
        </div>
      </footer>

      <style>{`input[type="date"]::-webkit-calendar-picker-indicator { filter: opacity(0.6); }`}</style>
    </div>
  )
}
