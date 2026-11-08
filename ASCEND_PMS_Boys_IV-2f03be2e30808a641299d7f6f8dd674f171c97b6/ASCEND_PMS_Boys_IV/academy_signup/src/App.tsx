import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import gsap from "gsap"
import BirdMascot from "./components/BirdMascot"

type FormDataType = {
  admissionNo: string
  activationCode: string
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
  schoolName: string
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
  "Pakistan": ["Khyber Pakhtunkhwa", "Punjab", "Sindh", "Balochistan", "Islamabad Capital Territory", "Gilgit-Baltistan", "Azad Jammu and Kashmir"],
  "United States": ["California", "New York", "Texas", "Florida", "Illinois", "Washington", "Massachusetts", "Colorado"],
  "United Kingdom": ["England", "Scotland", "Wales", "Northern Ireland", "Greater London", "West Midlands"],
  "Canada": ["Ontario", "Quebec", "British Columbia", "Alberta", "Manitoba", "Nova Scotia"],
  "Australia": ["New South Wales", "Victoria", "Queensland", "Western Australia", "South Australia", "Tasmania"],
  "India": ["Maharashtra", "Karnataka", "Tamil Nadu", "Delhi", "West Bengal", "Gujarat", "Kerala", "Rajasthan"],
  "UAE": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah"],
}

const programOptions = ["O-Level", "A-Level"]
const subjectOptions = ["Maths", "Computer Science"]
const gradeOptionsByProgram: Record<string, string[]> = {
  "O-Level": ["O-Level - Grade 9", "O-Level - Grade 10", "O-Level - Grade 11"],
  "A-Level": ["A-Level - AS (Grade 12)", "A-Level - A2 (Grade 13)"],
}

const BIRD = 260
const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v))

export default function App() {
  const [step, setStep] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState("")
  const registrationEnabled = document.getElementById("root")?.dataset.registrationEnabled === "1"
  const [focusedField, setFocusedField] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
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
    admissionNo: "",
    activationCode: "",
    fullName: "",
    email: "",
    phone: "",
    countryCode: "+92",
    gender: "",
    dob: "",
    guardianName: "",
    guardianPhone: "",
    country: "",
    province: "",
    program: "O-Level",
    subjects: ["Maths", "Computer Science"],
    schoolName: "",
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
      gsap.to(progressRef.current, { width: `${(step / 4) * 100}%`, duration: 0.6, ease: "power3.out" })
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
      if (!formData.phone.trim()) e.phone = "Required"
      if (!formData.gender) e.gender = "Required"
      if (!formData.dob || formData.dob > new Date().toISOString().slice(0, 10)) e.dob = "Enter a valid date of birth"
    }
    if (s === 2) {
      if (!formData.guardianName.trim()) e.guardianName = "Required"
      if (!formData.guardianPhone.trim()) e.guardianPhone = "Required"
      if (!formData.country) e.country = "Required"
      if (!formData.province) e.province = "Required"
    }
    if (s === 3) {
      if (!formData.schoolName.trim()) e.schoolName = "Required"
      if (!formData.schoolRegion.trim()) e.schoolRegion = "Required"
      if (!formData.schoolType) e.schoolType = "Required"
      if (!formData.grade) e.grade = "Required"
      if (!formData.program) e.program = "Required"
      if (formData.subjects.length === 0) e.subjects = "Pick at least one"
    }
    if (s === 4) {
      if (!/^[A-Za-z]{1,4}-\d{3,6}$/.test(formData.admissionNo.trim())) e.admissionNo = "Enter a valid admission number, e.g. A-6738"
      if (!formData.activationCode.trim()) e.activationCode = "Activation code required"
      if (formData.password.length < 8 || formData.password.length > 128 || !/[A-Za-z]/.test(formData.password) || !/\d/.test(formData.password)) e.password = "Use 8–128 characters with letters and numbers"
      if (formData.password !== formData.confirmPassword) e.confirmPassword = "Passwords must match"
      if (!formData.terms) e.terms = "Must accept"
      if (formData.captcha.trim() !== String(captchaA + captchaB)) e.captcha = "Incorrect"
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleContinue = async () => {
    if (submitting) return
    if (validateStep(step)) {
      if (step !== 4) { animateStepChange(step + 1); return }
      setSubmitting(true)
      setServerError("")
      try {
        const body = new FormData()
        const root = document.getElementById("root")
        // The cookie may have been refreshed by another tab after this page loaded.
        const csrfCookie = document.cookie.split("; ").find(cookie => cookie.startsWith("pms_csrf="))
        const csrfToken = csrfCookie ? decodeURIComponent(csrfCookie.slice("pms_csrf=".length)) : root?.dataset.csrfToken || ""
        body.append("csrf_token", csrfToken)
        body.append("profile", JSON.stringify(formData))
        const response = await fetch("/register/academy", { method: "POST", body })
        if (response.status === 403) {
          setServerError("Your security session could not be verified. Open this page in a new browser tab, allow cookies, and try again.")
          return
        }
        const result = await response.json().catch(() => null)
        if (!response.ok) { setServerError(result?.detail || "Unable to activate your account. Please try again."); return }
        window.location.assign("/student")
      } catch {
        setServerError("Could not connect. Please check your connection and try again.")
      } finally { setSubmitting(false) }
    }
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
    <div className="min-h-screen bg-white text-[#1A1A1A] selection:bg-[#C20A0A] selection:text-white overflow-x-hidden" style={{ fontFamily: "Inter, system-ui, sans-serif" }}>
      {/* Ambient page light (pure white base + soft premium tint) */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -top-40 -left-32 w-[520px] h-[520px] rounded-full bg-[#C20A0A]/[0.055] blur-[110px]" />
        <div className="absolute top-[30%] -right-40 w-[480px] h-[480px] rounded-full bg-[#C20A0A]/[0.06] blur-[120px]" />
        <div className="absolute bottom-0 left-1/3 w-[420px] h-[420px] rounded-full bg-[#C20A0A]/[0.04] blur-[120px]" />
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
              <div className="w-9 h-9 rounded-xl bg-[#C20A0A] flex items-center justify-center text-white font-black text-[16px] tracking-tighter shadow-[0_6px_16px_rgba(194,10,10,0.28)]">A</div>
              <span className="font-extrabold text-[18px] tracking-tight" style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}>ASCEND</span>
              <span className="hidden sm:inline text-[11px] font-bold tracking-widest text-black/40 ml-1">ACADEMY</span>
            </div>
            <nav className="hidden lg:flex items-center gap-6 text-[13px] font-semibold text-black/60">
              <a className="text-black" href="/">Home</a>
              <a href="/about">About</a>
              <a href="/privacy">Privacy</a>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 text-[12px] font-semibold text-black/60">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              {registrationEnabled ? "Student registration open" : "Student registration closed"}
            </div>
            <a href="/login" className="px-4 py-2 rounded-full border border-black/10 text-[13px] font-bold">Sign in</a>

          </div>
        </div>
        <div className="h-[3px] bg-black/[0.06] w-full">
          <div ref={progressRef} className="h-full bg-[#C20A0A] w-[25%]" />
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-[860px] px-4 sm:px-6 py-8 sm:py-12">
        {!registrationEnabled ? (
          <div className="bg-white rounded-3xl border border-black/10 shadow-xl p-8 text-center">
            <h1 className="text-2xl font-extrabold">Student registration is currently closed</h1>
            <p className="mt-3 text-black/60">Please contact the school office for help activating your account.</p>
            <a href="/login" className="inline-block mt-6 text-[#C20A0A] font-bold">Return to sign in</a>
          </div>
        ) : (
          <div>
            {/* Form Card */}
            <div className="bg-white rounded-[24px] shadow-[0_24px_70px_rgba(0,0,0,0.09)] border border-black/[0.07] overflow-hidden">
              <div className="px-6 sm:px-8 pt-6 sm:pt-8 pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-full bg-[#FFF0F0] border border-[#C20A0A]/20 text-[#C20A0A] text-[11px] font-extrabold tracking-widest">STEP {step} OF 4</span>
                    <span className="hidden sm:inline text-[12px] font-semibold text-black/40">• {step === 3 ? "O/A Levels only" : "Registration"}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {[1, 2, 3, 4].map(i => (
                      <div key={i} className={`h-1.5 rounded-full transition-all duration-500 ${i === step ? "w-8 bg-[#C20A0A]" : i < step ? "w-6 bg-[#C20A0A]/60" : "w-6 bg-black/10"}`} />
                    ))}
                  </div>
                </div>
              </div>

              <div ref={formContainerRef} className="px-6 sm:px-8 pb-8">
                {step === 1 && (
                  <div className="pt-4">
                    <h1 className="text-[28px] sm:text-[32px] font-extrabold tracking-tight leading-none" style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}>
                      Create your <span className="text-[#C20A0A]">profile</span>
                    </h1>
                    <p className="text-[13.5px] text-black/60 font-medium mt-2">Tell us about yourself — our bird will peek when you type! 🐦</p>

                    <div className="mt-7 space-y-4">
                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">FULL NAME *</label>
                        <div className={`mt-1.5 relative flex items-center border-2 rounded-xl px-3 py-2.5 bg-white transition-all ${focusedField === "fullName" ? "border-[#C20A0A] shadow-[0_0_0_4px_rgba(194,10,10,0.08)]" : errors.fullName ? "border-red-400" : "border-black/10"}`}>
                          <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3 text-black/60">◉</span>
                          <input onFocus={e => onFieldFocus("fullName", e.currentTarget)} onBlur={onFieldBlur} value={formData.fullName} onChange={e => updateField("fullName", e.target.value)} placeholder="Alex Morgan" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                        </div>
                        {errors.fullName && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.fullName}</p>}
                      </div>

                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">EMAIL ADDRESS *</label>
                        <div className={`mt-1.5 relative flex items-center border-2 rounded-xl px-3 py-2.5 bg-white transition-all ${focusedField === "email" ? "border-[#C20A0A] shadow-[0_0_0_4px_rgba(194,10,10,0.08)]" : errors.email ? "border-red-400" : "border-black/10"}`}>
                          <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3 text-black/60">✉</span>
                          <input onFocus={e => onFieldFocus("email", e.currentTarget)} onBlur={onFieldBlur} value={formData.email} onChange={e => updateField("email", e.target.value)} placeholder="alex@email.com" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" type="email" />
                        </div>
                        {errors.email && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.email}</p>}
                      </div>

                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">PHONE NUMBER *</label>
                        <div className={`mt-1.5 flex items-center border-2 rounded-xl bg-white overflow-hidden transition-all ${focusedField === "phone" ? "border-[#C20A0A] shadow-[0_0_0_4px_rgba(194,10,10,0.08)]" : "border-black/10"}`}>
                          <select value={formData.countryCode} onChange={e => updateField("countryCode", e.target.value)} className="px-3 py-2.5 bg-black/[0.04] border-r border-black/10 text-[13px] font-bold outline-none">
                            <option>+92</option><option>+1</option><option>+44</option><option>+91</option><option>+61</option><option>+971</option>
                          </select>
                          <input onFocus={e => onFieldFocus("phone", e.currentTarget)} onBlur={onFieldBlur} value={formData.phone} onChange={e => updateField("phone", e.target.value)} placeholder="(555) 000-0000" className="flex-1 px-3 py-2.5 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                        </div>
                        {errors.phone && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.phone}</p>}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="text-[11px] font-extrabold tracking-widest text-black/60">GENDER *</label>
                          <div className={`mt-1.5 relative border-2 rounded-xl px-3 py-2.5 flex items-center justify-between bg-white ${focusedField === "gender" ? "border-[#C20A0A]" : errors.gender ? "border-red-400" : "border-black/10"}`}>
                            <select onFocus={e => onFieldFocus("gender", e.currentTarget)} onBlur={onFieldBlur} value={formData.gender} onChange={e => updateField("gender", e.target.value)} className="flex-1 bg-transparent outline-none text-[14px] font-semibold text-black/80">
                              <option value="">Select gender</option>
                              <option>Female</option><option>Male</option><option>Non-binary</option><option>Prefer not to say</option>
                            </select>
                          </div>
                          {errors.gender && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.gender}</p>}
                        </div>
                        <div>
                          <label className="text-[11px] font-extrabold tracking-widest text-black/60">DATE OF BIRTH *</label>
                          <div className={`mt-1.5 border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "dob" ? "border-[#C20A0A]" : errors.dob ? "border-red-400" : "border-black/10"}`}>
                            <input onFocus={e => onFieldFocus("dob", e.currentTarget)} onBlur={onFieldBlur} value={formData.dob} onChange={e => updateField("dob", e.target.value)} type="date" className="w-full bg-transparent outline-none text-[14px] font-semibold" />
                          </div>
                          {errors.dob && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.dob}</p>}
                        </div>
                      </div>

                      <button onClick={handleContinue} className="w-full mt-2 h-[52px] rounded-xl bg-[#C20A0A] text-white font-extrabold text-[14px] tracking-wide shadow-[0_10px_24px_rgba(194,10,10,0.3)] hover:bg-[#A80808] active:scale-[0.99] transition-all">
                        Continue →
                      </button>
                      <p className="text-center text-[11px] font-semibold text-black/40">Fly with us — O & A Levels only 🐦</p>
                    </div>
                  </div>
                )}

                {step === 2 && (
                  <div className="pt-4">
                    <h2 className="text-[26px] font-extrabold tracking-tight" style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}>Guardian & Location</h2>
                    <p className="text-[13px] text-black/60 font-medium mt-1">Guardian details + location. State list adapts to your country ✨</p>

                    <div className="mt-6 space-y-5">
                      <div className="rounded-2xl bg-[#FFF6F6] border border-[#C20A0A]/10 p-4">
                        <div className="flex items-center gap-2">
                          <span className="w-7 h-7 rounded-full bg-[#C20A0A] text-white flex items-center justify-center text-[12px] font-black">1</span>
                          <h3 className="text-[13px] font-extrabold tracking-wide">Guardian / Parent Details</h3>
                        </div>
                        <div className="mt-4 space-y-3">
                          <div>
                            <label className="text-[11px] font-extrabold tracking-widest text-black/60">FATHER'S / GUARDIAN'S NAME *</label>
                            <div className={`mt-1.5 flex items-center border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "guardianName" ? "border-[#C20A0A]" : errors.guardianName ? "border-red-400" : "border-black/10"}`}>
                              <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3">👤</span>
                              <input onFocus={e => onFieldFocus("guardianName", e.currentTarget)} onBlur={onFieldBlur} value={formData.guardianName} onChange={e => updateField("guardianName", e.target.value)} placeholder="Sarah Johnson" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                            </div>
                            {errors.guardianName && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.guardianName}</p>}
                          </div>
                          <div>
                            <label className="text-[11px] font-extrabold tracking-widest text-black/60">GUARDIAN CONTACT NUMBER *</label>
                            <div className={`mt-1.5 flex items-center border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "guardianPhone" ? "border-[#C20A0A]" : errors.guardianPhone ? "border-red-400" : "border-black/10"}`}>
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
                          <span className="ml-auto text-[10px] font-black tracking-widest bg-[#FFF0F0] text-[#C20A0A] px-2 py-1 rounded-full">{formData.country ? `${availableStates.length} states` : "Pick country first"}</span>
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
                        <button onClick={handleContinue} className="flex-1 h-[48px] rounded-xl bg-[#C20A0A] text-white font-extrabold text-[14px] shadow-[0_10px_24px_rgba(194,10,10,0.25)] hover:bg-[#A80808] transition">Continue →</button>
                      </div>
                    </div>
                  </div>
                )}

                {step === 3 && (
                  <div className="pt-4">
                    <h2 className="text-[22px] sm:text-[26px] font-extrabold tracking-tight leading-tight" style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}>Program, School & Subjects</h2>
                    <p className="text-[12.5px] text-black/55 font-medium mt-2 leading-relaxed">Step 3 of 4 — <span className="text-[#C20A0A] font-bold">Only O-Level & A-Level</span>. Subjects limited to <span className="font-bold">Maths & Computer Science</span>.</p>

                    <div className="mt-5">
                      <label className="text-[11px] font-extrabold tracking-widest text-black/60">PROGRAM * — Choose one</label>
                      <div className="mt-2 grid grid-cols-2 gap-3">
                        {programOptions.map(p => (
                          <button key={p} onClick={() => selectProgram(p)} type="button" className={`rounded-xl border-2 px-4 py-3 text-left transition ${formData.program === p ? "border-[#C20A0A] bg-[#FFF0F0] shadow-[0_4px_12px_rgba(194,10,10,0.12)]" : "border-black/10 bg-white hover:border-black/20"}`}>
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
                            <button key={sub} onClick={() => toggleSubject(sub)} className={`flex-1 py-2.5 rounded-full text-[13.5px] font-extrabold border-2 transition flex items-center justify-center gap-2 ${active ? "bg-[#C20A0A] text-white border-[#C20A0A] shadow-[0_6px_16px_rgba(194,10,10,0.25)]" : "bg-white text-black/50 border-black/10"}`}>
                              {active ? "✓ " : "+ "}{sub}
                            </button>
                          )
                        })}
                      </div>
                      <p className="text-[11px] font-semibold text-black/40 mt-2">No other subjects available — focused curriculum for excellence.</p>
                      {errors.subjects && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.subjects}</p>}
                    </div>

                    <div className="mt-5 p-4 rounded-2xl border border-black/10 bg-[#FFFBFB]">
                      <h4 className="text-[12px] font-extrabold tracking-widest text-black/70">WHERE YOU STUDY</h4>
                      <div className="mt-3">
                        <label className="text-[11px] font-bold text-black/60">School name *</label>
                        <input value={formData.schoolName} onChange={e => updateField("schoolName", e.target.value)} maxLength={200} placeholder="Enter your school name" className={`mt-1.5 w-full border-2 rounded-xl px-3 py-2.5 text-[13px] font-semibold outline-none bg-white ${errors.schoolName ? "border-red-400" : "border-black/10"}`} />
                        {errors.schoolName && <p className="text-[11px] text-red-500 font-bold mt-1">{errors.schoolName}</p>}
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                        <div>
                          <label className="text-[11px] font-bold text-black/60">School state / region *</label>
                          <input value={formData.schoolRegion} onChange={e => updateField("schoolRegion", e.target.value)} onFocus={e => onFieldFocus("schoolRegion", e.currentTarget)} onBlur={onFieldBlur} placeholder="e.g. California" className={`mt-1.5 w-full border-2 rounded-xl px-3 py-2.5 text-[13px] font-semibold outline-none bg-white ${focusedField === "schoolRegion" ? "border-[#C20A0A]" : errors.schoolRegion ? "border-red-400" : "border-black/10"}`} />
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
                      <button onClick={handleContinue} className="flex-1 h-[48px] rounded-xl bg-[#C20A0A] text-white font-extrabold text-[14px] shadow-[0_10px_24px_rgba(194,10,10,0.25)]">Continue →</button>
                    </div>
                  </div>
                )}

                {step === 4 && (
                  <div className="pt-4">
                    <h2 className="text-[26px] font-extrabold tracking-tight" style={{ fontFamily: "Plus Jakarta Sans, sans-serif" }}>Password & Finish</h2>
                    <p className="text-[13px] text-black/60 font-medium mt-1">Step 4 of 4 — Lock it in! The bird is on guard 🔐</p>

                    <div className="mt-6 space-y-4">
                      <p className="text-[13px] text-black/60">Use the admission number and activation code provided by your school to connect your account to your student dashboard.</p>
                      <div>
                        <label htmlFor="admissionNo" className="text-[11px] font-extrabold tracking-widest text-black/60">ADMISSION NUMBER *</label>
                        <input id="admissionNo" value={formData.admissionNo} onChange={e => updateField("admissionNo", e.target.value)} placeholder="A-6738" autoComplete="username" className="mt-1.5 w-full border-2 border-black/10 rounded-xl px-3 py-3 text-[14px] font-semibold" />
                        {errors.admissionNo && <p className="text-[11px] text-red-500 font-bold">{errors.admissionNo}</p>}
                      </div>
                      <div>
                        <label htmlFor="activationCode" className="text-[11px] font-extrabold tracking-widest text-black/60">ACTIVATION CODE *</label>
                        <input id="activationCode" value={formData.activationCode} onChange={e => updateField("activationCode", e.target.value)} placeholder="School-issued code" className="mt-1.5 w-full border-2 border-black/10 rounded-xl px-3 py-3 text-[14px] font-semibold" />
                        {errors.activationCode && <p className="text-[11px] text-red-500 font-bold">{errors.activationCode}</p>}
                      </div>
                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">PASSWORD *</label>
                        <div className={`mt-1.5 flex items-center border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "password" ? "border-[#C20A0A]" : errors.password ? "border-red-400" : "border-black/10"}`}>
                          <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3">🔒</span>
                          <input type="password" onFocus={e => onFieldFocus("password", e.currentTarget)} onBlur={onFieldBlur} value={formData.password} onChange={e => updateField("password", e.target.value)} placeholder="Create a strong password" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                        </div>
                        <p className="text-[11px] font-semibold text-black/40 mt-1">8–128 characters, including letters and numbers</p>
                        {errors.password && <p className="text-[11px] text-red-500 font-bold">{errors.password}</p>}
                      </div>

                      <div>
                        <label className="text-[11px] font-extrabold tracking-widest text-black/60">CONFIRM PASSWORD *</label>
                        <div className={`mt-1.5 flex items-center border-2 rounded-xl px-3 py-2.5 bg-white ${focusedField === "confirmPassword" ? "border-[#C20A0A]" : errors.confirmPassword ? "border-red-400" : "border-black/10"}`}>
                          <span className="w-8 h-8 rounded-lg bg-black/[0.04] flex items-center justify-center mr-3">🔒</span>
                          <input type="password" onFocus={e => onFieldFocus("confirmPassword", e.currentTarget)} onBlur={onFieldBlur} value={formData.confirmPassword} onChange={e => updateField("confirmPassword", e.target.value)} placeholder="Repeat password" className="flex-1 outline-none text-[14px] font-semibold placeholder:text-black/30 bg-transparent" />
                        </div>
                        <p className="text-[11px] font-semibold text-black/40 mt-1">8–128 characters, including letters and numbers</p>
                        {errors.confirmPassword && <p className="text-[11px] text-red-500 font-bold">{errors.confirmPassword}</p>}
                      </div>

                      <label className="flex items-start gap-3 p-3 rounded-xl border border-black/10 bg-[#FFFBFB] cursor-pointer">
                        <input type="checkbox" checked={formData.terms} onChange={e => updateField("terms", e.target.checked)} className="mt-1 w-4 h-4 accent-[#C20A0A]" />
                        <span className="text-[12.5px] font-semibold leading-relaxed">I have read and accept the <a href="/privacy" target="_blank" rel="noreferrer" className="text-[#C20A0A] underline font-bold">privacy policy</a>. *</span>
                      </label>
                      {errors.terms && <p className="text-[11px] text-red-500 font-bold -mt-2">{errors.terms}</p>}

                      <div className="rounded-xl border-2 border-black/10 bg-white p-4 flex items-center justify-between gap-4">
                        <div>
                          <p className="text-[11px] font-extrabold tracking-widest text-black/60">SECURITY CHECK *</p>
                          <p className="text-[16px] font-black mt-1">{captchaA} + {captchaB} = <span className="text-[#C20A0A]">?</span></p>
                        </div>
                        <input value={formData.captcha} onChange={e => updateField("captcha", e.target.value)} placeholder="Answer" onFocus={e => onFieldFocus("captcha", e.currentTarget)} onBlur={onFieldBlur} className={`w-24 h-12 rounded-xl border-2 text-center text-[16px] font-black outline-none bg-[#FFF6F6] ${errors.captcha ? "border-red-400" : focusedField === "captcha" ? "border-[#C20A0A]" : "border-black/10"}`} />
                      </div>
                      {errors.captcha && <p className="text-[11px] text-red-500 font-bold">{errors.captcha}</p>}

                      {serverError && <div role="alert" className="text-sm text-red-700 font-bold"><p>{serverError}</p><a href="/register" target="_blank" rel="noreferrer" className="underline">Open registration in a new tab</a></div>}
                      <div className="flex gap-3 pt-2">
                        <button onClick={() => animateStepChange(3)} className="px-6 h-[48px] rounded-xl border border-black/10 bg-white font-bold text-[13px]">← Previous</button>
                        <button onClick={handleContinue} disabled={submitting} className="disabled:opacity-50 flex-1 h-[56px] rounded-xl bg-[#C20A0A] text-white font-black text-[15px] tracking-wide shadow-[0_12px_28px_rgba(194,10,10,0.3)] hover:bg-[#A80808] transition">{submitting ? "Activating…" : "Activate & open dashboard ✨"}</button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <p className="text-center text-[11px] font-semibold text-black/30 mt-4">🔒 Secure student account activation</p>
          </div>
        )}
      </main>

      <footer className="relative z-10 border-t border-black/5 bg-white/70 backdrop-blur mt-8">
        <div className="mx-auto max-w-[1280px] px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-bold tracking-widest text-black/30">
          <span>© ASCEND • STUDENT REGISTRATION</span>
          <span className="flex items-center gap-3"><a href="/privacy">Privacy</a> <a href="/about">About</a></span>
        </div>
      </footer>

      <style>{`input[type="date"]::-webkit-calendar-picker-indicator { filter: opacity(0.6); }`}</style>
    </div>
  )
}
