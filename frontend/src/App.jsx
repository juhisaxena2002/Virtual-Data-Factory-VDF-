import React, { useState } from "react";
import { AppProvider } from "./context/AppContext";
import Sidebar from "./components/sidebar/Sidebar";
import ChatArea from "./components/chat/ChatArea";
import ChatInput from "./components/chat/ChatInput";
import RightPanel from "./components/rightpanel/RightPanel";
import "./index.css";
import Login from "./components/login";

function MainApp() {
  return (
    <AppProvider>
      <div style={styles.shell}>
        <Sidebar />
        <main style={styles.main}>
          <ChatArea />
          <ChatInput />
        </main>
        <RightPanel />
      </div>
    </AppProvider>
  );
}

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(
    () => localStorage.getItem("vdf_auth") === "true"
  );

  const handleLoginSuccess = () => {
    localStorage.setItem("vdf_auth", "true");
    setIsLoggedIn(true);
  };

  if (!isLoggedIn) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return <MainApp />;
}

const styles = {
  shell: {
    display: "flex",
    height: "100vh",
    width: "100vw",
    overflow: "hidden",
    fontFamily: "'DM Sans', sans-serif",
    background: "#fff",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    minWidth: 0,
  },
};
