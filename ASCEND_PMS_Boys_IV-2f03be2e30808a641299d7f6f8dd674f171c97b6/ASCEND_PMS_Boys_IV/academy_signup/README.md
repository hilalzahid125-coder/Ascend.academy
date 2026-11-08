# Academy registration

This is the source of the registration UI supplied with the academy signup ZIP. The FastAPI app serves the built assets from `static/academy-signup`, so Node is not needed at runtime. After editing this UI, run:

```sh
cd academy_signup
npm ci
npm run build
```

Commit the rebuilt assets along with the source. Registration still requires an enabled registration setting and a school-issued admission number and activation code. Submitted details are stored separately from the school-managed student record; successful activation signs the student into the existing dashboard.
