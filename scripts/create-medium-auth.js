(() => {
  const expires = Math.floor(Date.now() / 1000) + 30 * 24 * 60 * 60;
  const cookieNames = ["sid", "uid", "xsrf", "cf_clearance"];
  const seen = new Set();

  const parseCookies = () =>
    document.cookie
      .split(";")
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => {
        const index = item.indexOf("=");
        return [item.slice(0, index), item.slice(index + 1)];
      });

  const cookie = (name, value) => ({
    name,
    value,
    domain: ".medium.com",
    path: "/",
    expires,
    httpOnly: false,
    secure: true,
    sameSite: "Lax",
  });

  const cookies = [];
  for (const [name, value] of parseCookies()) {
    if (!cookieNames.includes(name) && !name.startsWith("cf_")) continue;
    if (seen.has(name)) continue;
    seen.add(name);
    cookies.push(cookie(name, decodeURIComponent(value)));
  }

  const origins = [
    {
      origin: "https://medium.com",
      localStorage: Object.keys(localStorage).map((name) => ({
        name,
        value: localStorage.getItem(name),
      })),
    },
  ];

  const authState = { cookies, origins };
  const json = JSON.stringify(authState, null, 2);

  const warning = cookies.some((item) => item.name === "sid")
    ? ""
    : "\n\nWARNING: no sid cookie was visible to JavaScript. If Medium marks sid as HttpOnly in your browser, this console snippet cannot read it; copy sid manually from DevTools > Application > Cookies and add it to cookies[].";

  const done = () => console.log(`medium-auth.json copied to clipboard.${warning}`, authState);

  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(json).then(done);
  } else {
    copy(json);
    done();
  }
})();
