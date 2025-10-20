import Output from "./components/Output";
import TextArea from "./components/TextArea";
import { type ChatOutput } from "./types";
import { useState } from "react";

export default function App() {
  const [outputs, setOutputs] = useState<ChatOutput[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div
        className={`container pt-10 pb-32 min-h-screen ${outputs.length === 0 && "flex items-center justify-center"
          }`}
      >
        <div className="container">
          {outputs.length === 0 && (
            <h1 className="text-4xl text-center mb-5">
              What do you want to know?
            </h1>
          )}



          {outputs.map((output, i) => {
            return <Output key={i} output={output} />;
          })}

          <TextArea
            setIsGenerating={setIsGenerating}
            isGenerating={isGenerating}
            outputs={outputs}
            setOutputs={setOutputs}
          />
        </div>
      </div>
    </div>
  );
}